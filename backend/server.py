from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
import shutil
import json
import glob
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import BackgroundTasks
import base64
from cryptography.fernet import Fernet
import io
import zipfile

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Encryption for API keys
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key for secure storage"""
    return base64.b64encode(cipher_suite.encrypt(api_key.encode())).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key for use"""
    return cipher_suite.decrypt(base64.b64decode(encrypted_key.encode())).decode()

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT and Password configuration
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'pergaminos-secret-key-2025')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI(title="Pergaminos Digitalization API")

# File upload limits
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB per file
MAX_BATCH_SIZE = 1024 * 1024 * 1024  # 1 GB per batch

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Utility functions for password hashing
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Ensure backward compatibility with users missing new fields
    if 'company_ids' not in user:
        user['company_ids'] = []
    if 'assigned_corporation' not in user:
        user['assigned_corporation'] = None
    
    return User(**user)

# Pydantic Models
class UserRole(BaseModel):
    role: str  # "staff", "asesor", or "client"

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str  # "staff", "asesor", or "client"
    company_id: Optional[str] = Field(default=None)  # Deprecated: use company_ids instead
    company_ids: List[str] = Field(default_factory=list)  # Multiple companies for client users
    assigned_corporation: Optional[str] = Field(default=None)  # Corporation assignment for client users
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str  # "staff", "asesor", or "client"
    company_id: Optional[str] = Field(default=None)  # Deprecated: use company_ids instead
    company_ids: List[str] = Field(default_factory=list)  # Multiple companies for client users
    assigned_corporation: Optional[str] = Field(default=None)  # Corporation assignment for client users

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Segmento(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nombre: str
    descripcion: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # staff user id

class SegmentoCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class Corporation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # staff user id who created it
    usage_count: int = 0  # Track how many companies use this corporation

class CorporationCreate(BaseModel):
    name: str

class ExtractedData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str  # Cliente al que pertenecen los datos
    project_id: str  # Proyecto del que se extrajeron
    document_id: str  # Documento fuente
    document_name: str  # Nombre del documento para referencia
    field_name: str  # Nombre del campo extraído (ej: "nit", "fecha", "valor")
    field_value: str  # Valor extraído
    field_type: Optional[str] = None  # Tipo de dato (text, number, date, email, etc.)
    confidence: Optional[float] = None  # Confianza de la extracción (0-1)
    page_number: Optional[int] = None  # Página donde se encontró
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_method: str = "ai_extraction"  # ai_extraction, manual_input, etc.
    
class ExtractedDataSummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    project_id: str
    document_id: str
    summary_data: Dict[str, Any]  # Resumen consolidado del documento
    total_fields: int
    extraction_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIConfiguration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # Configuración por proyecto
    config_type: str  # "data_extraction", "qa_processing", "document_processing"
    provider: str = "openai"  # openai, emergent
    api_key: Optional[str] = None  # Encrypted storage recommended
    model_name: str  # Specific model for the task
    model_parameters: Dict[str, Any] = {}  # Additional model parameters
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # Staff user who configured

class AIConfigurationCreate(BaseModel):
    config_type: str
    provider: str = "openai"
    api_key: Optional[str] = None
    model_name: str
    model_parameters: Dict[str, Any] = {}

class AIConfigurationUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    model_parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

# OCR Configuration (Global)
class OCRConfig(BaseModel):
    id: str = "global_ocr_config"  # Single global configuration
    ocr_enabled: bool = False  # Enable/disable OCR globally
    ocr_method: str = "gpt4o_vision"  # "tesseract" or "gpt4o_vision"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None  # Staff user who updated

class OCRConfigUpdate(BaseModel):
    ocr_enabled: Optional[bool] = None  # Enable/disable OCR
    ocr_method: Optional[str] = None  # "tesseract" or "gpt4o_vision"

# Contact model for companies
class Contact(BaseModel):
    nombre: str
    email: EmailStr
    telefono: str

class Company(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # Nombre comercial
    razon_social: Optional[str] = None
    nombre_comercial: Optional[str] = None  # Duplicado de name para claridad
    nit: Optional[str] = None
    description: Optional[str] = None
    contacto: Optional[str] = None  # Nombre del contacto
    contact_email: Optional[EmailStr] = None  # Keep for backward compatibility
    telefono: Optional[str] = None  # Keep for backward compatibility
    contactos: List[Contact] = []  # New: multiple contacts
    direccion: Optional[str] = None
    asesor_comercial_id: Optional[str] = None  # ID del usuario asesor
    segmento: Optional[str] = None  # Industria/segmento
    corporacion: Optional[str] = None  # Corporación (texto libre)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # staff user id

class CompanyCreate(BaseModel):
    name: str  # Nombre comercial (requerido)
    razon_social: Optional[str] = None
    nit: Optional[str] = None
    description: Optional[str] = None
    contacto: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    contactos: Optional[List[Contact]] = []  # New: multiple contacts
    direccion: Optional[str] = None
    asesor_comercial_id: Optional[str] = None
    segmento: Optional[str] = None
    corporacion: Optional[str] = None
    is_active: Optional[bool] = True

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_code: Optional[str] = None  # Custom alphanumeric ID defined by user
    name: str
    description: Optional[str] = None
    company_id: str
    status: str = "active"  # active, completed, paused
    is_active: bool = True  # Toggle to activate/deactivate project
    semantic_instructions: Optional[str] = None  # Instructions for AI processing
    pdf_history_retention_months: int = 6  # How long to keep PDF history (3, 6, or 12 months)
    pdf_history_retention_until: Optional[datetime] = None  # Manual extension date
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # user id

class ProjectCreate(BaseModel):
    project_code: Optional[str] = None  # Custom alphanumeric ID
    name: str
    description: Optional[str] = None
    company_id: str
    is_active: bool = True  # Toggle to activate/deactivate project
    semantic_instructions: Optional[str] = None
    pdf_history_retention_months: int = 6
    pdf_history_retention_until: Optional[datetime] = None

class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str
    project_id: str
    file_path: str
    status: str = "uploaded"  # uploaded, qa_pending, qa_failed, qa_passed, processing, completed, failed, needs_review
    extracted_data: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None
    display_order: Optional[int] = None  # For reordering
    reorder_reasoning: Optional[str] = None  # AI reasoning for reorder
    reordered_at: Optional[datetime] = None  # When reordered
    # Chunk processing fields
    total_pages: Optional[int] = None
    chunk_count: Optional[int] = None
    chunks_processed: Optional[int] = 0
    chunk_results: Optional[List[Dict[str, Any]]] = None
    processing_progress: Optional[int] = 0  # 0-100
    processing_message: Optional[str] = None  # Progress message for user
    # QA fields
    qa_status: Optional[str] = None  # pending, passed, failed, manual_review
    qa_results: Optional[Dict[str, Any]] = None  # QA agent results
    qa_findings: Optional[List[Dict[str, Any]]] = None  # Important findings for manual review
    qa_processed_at: Optional[datetime] = None
    qa_approved_by: Optional[str] = None  # Staff user who approved after manual review
    qa_approved_at: Optional[datetime] = None
    qa_review_comments: Optional[str] = None  # Comments from reviewer
    qa_review_action: Optional[str] = None  # "approved" or "rejected"
    qa_reviewed_by_name: Optional[str] = None  # Name of reviewer for display
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by: str  # user id

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: User

class BatchProcessTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    document_ids: List[str]
    status: str = "pending"  # pending, processing, completed, failed
    progress: int = 0  # 0-100
    completed_documents: int = 0
    failed_documents: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# PDF Manager Models
class RenameOperation(BaseModel):
    from_id: str  # Document ID
    from_name: str  # Current name
    to_name: str  # New name
    reasoning: Optional[str] = None  # AI reasoning for the rename

class PlanValidation(BaseModel):
    confidence: float  # 0.0 to 1.0
    conflicts: List[str] = []  # List of conflict descriptions
    warnings: List[str] = []  # Non-blocking warnings

class PDFManagerPlan(BaseModel):
    rename_operations: List[RenameOperation] = []
    reorder_ids: List[str] = []  # Ordered list of document IDs
    validation: PlanValidation

class PDFManagerJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    project_id: str
    instruction: str  # Natural language instruction
    plan: Optional[PDFManagerPlan] = None
    status: str = "pending"  # pending, planning, plan_ready, executing, completed, failed
    result_urls: Optional[Dict[str, Any]] = None  # {files: [{id, name, url}], zip_url}
    error_message: Optional[str] = None
    logs: List[Dict[str, Any]] = []
    created_by: str  # User ID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class PDFManagerPlanRequest(BaseModel):
    project_id: str
    instruction: str

# PDF Page Manager Models
class PageReorderOperation(BaseModel):
    page_number: int  # Original page number
    new_position: int  # New position

class PDFPagePlan(BaseModel):
    pdf_filename: str  # The PDF file being reordered
    total_pages: int
    reorder_operations: List[PageReorderOperation] = []
    new_page_sequence: List[int] = []  # Final page order
    confidence: float  # 0.0 to 1.0
    reasoning: str  # AI explanation of the reordering logic

class PDFPageExtractPlan(BaseModel):
    pdf_filename: str
    total_pages: int
    pages_to_extract: List[int] = []  # Page numbers to extract (1-indexed)
    new_filename: str  # Name for the extracted PDF
    confidence: float  # 0.0 to 1.0
    reasoning: str  # AI explanation

class PDFPageManagerJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    project_id: str
    pdf_filename: str  # The specific PDF being processed
    instruction: str  # Natural language instruction
    mode: str = "reorder"  # "reorder" or "extract"
    plan: Optional[PDFPagePlan] = None  # For reorder mode
    extract_plan: Optional[PDFPageExtractPlan] = None  # For extract mode
    status: str = "pending"  # pending, plan_ready, executing, completed, failed
    result_url: Optional[str] = None  # URL to download reordered/extracted PDF
    result_filename: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[Dict[str, Any]] = []
    created_by: str  # User ID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class PDFPageManagerPlanRequest(BaseModel):
    project_id: str
    pdf_filename: str
    instruction: str
    mode: str = "reorder"  # "reorder" or "extract"
    manual_range: Optional[str] = None  # e.g., "1-20" or "1,5,10,15" for extract mode

# PDF History Model
class PDFHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    company_name: str
    project_id: str
    project_name: str
    operation_type: str  # "rename", "reorder", "extract"
    original_pdf_name: str
    original_pdf_path: Optional[str] = None  # Path to original PDF
    result_pdf_name: str
    result_pdf_path: str  # Path to processed PDF
    instruction: Optional[str] = None  # Natural language instruction used
    job_id: Optional[str] = None  # Reference to PDFManagerJob or PDFPageManagerJob
    performed_by: str  # User ID who performed the operation
    performed_by_name: str  # User name for display
    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    file_size: Optional[int] = None  # Size in bytes
    page_count: Optional[int] = None  # Number of pages in result PDF
    download_url: str  # URL to download the PDF

class RetentionPolicyConfig(BaseModel):
    id: str = "global_retention_policy"  # Single global configuration
    retention_months: int = 6  # 6 or 12 months
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None  # Staff user who updated

class RetentionPolicyUpdate(BaseModel):
    retention_months: int  # 6 or 12 months

# Create uploads directory - use absolute path to ensure consistency
UPLOAD_DIR = Path("/app/backend/uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
print(f"[INIT] Upload directory configured at: {UPLOAD_DIR}")

# Authentication endpoints
@api_router.post("/auth/register", response_model=User)
async def register_user(user_data: UserCreate, current_user: User = Depends(get_current_user)):
    # Only staff can create users
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can create users")
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate company assignments for client users
    if user_data.role == "client":
        # Handle backward compatibility: if company_id is set, add to company_ids
        if user_data.company_id and user_data.company_id not in user_data.company_ids:
            user_data.company_ids.append(user_data.company_id)
        
        # Validate all company_ids
        for company_id in user_data.company_ids:
            company = await db.companies.find_one({"id": company_id})
            if not company:
                raise HTTPException(status_code=400, detail=f"Company {company_id} not found")
        
        # Validate corporation if assigned
        if user_data.assigned_corporation:
            corp = await db.corporations.find_one({"name": user_data.assigned_corporation})
            if not corp:
                raise HTTPException(status_code=400, detail=f"Corporation {user_data.assigned_corporation} not found")
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user_dict = user_data.dict()
    del user_dict["password"]
    user = User(**user_dict)
    
    # Store user with hashed password
    user_doc = user.dict()
    user_doc["hashed_password"] = hashed_password
    await db.users.insert_one(user_doc)
    
    return user

@api_router.post("/auth/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    # Find user
    user_doc = await db.users.find_one({"email": login_data.email})
    if not user_doc or not verify_password(login_data.password, user_doc.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    user = User(**user_doc)
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")
    
    # Check if user's company is active (for client and asesor users)
    if user.role in ["client", "asesor"] and user.company_id:
        company = await db.companies.find_one({"id": user.company_id})
        if company and not company.get("is_active", True):
            raise HTTPException(
                status_code=403, 
                detail="Su empresa está inactiva. Contacte al administrador para más información."
            )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return TokenResponse(access_token=access_token, token_type="bearer", user=user)

@api_router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# Company management endpoints
@api_router.post("/companies", response_model=Company)
async def create_company(company_data: CompanyCreate, current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can create companies")
    
    company_dict = company_data.dict()
    company_dict["created_by"] = current_user.id
    company = Company(**company_dict)
    
    await db.companies.insert_one(company.dict())
    
    # Increment corporation usage count if corporation is set
    if company.corporacion:
        await db.corporations.update_one(
            {"name": company.corporacion},
            {"$inc": {"usage_count": 1}},
            upsert=False
        )
    
    return company

@api_router.get("/companies", response_model=List[Company])
async def get_companies(current_user: User = Depends(get_current_user)):
    logger.info(f"Get companies request from user: {current_user.email}, role: {current_user.role}")
    logger.info(f"User company_ids: {current_user.company_ids}, assigned_corporation: {current_user.assigned_corporation}")
    
    if current_user.role == "client":
        # Clients can see companies based on assignment
        query_conditions = []
        
        # Add companies from company_ids list
        if current_user.company_ids:
            query_conditions.append({"id": {"$in": current_user.company_ids}})
        
        # Add backward compatibility for single company_id
        elif current_user.company_id:
            query_conditions.append({"id": current_user.company_id})
        
        # Add companies from assigned corporation
        if current_user.assigned_corporation:
            query_conditions.append({"corporacion": current_user.assigned_corporation})
        
        # Combine conditions with $or
        if query_conditions:
            query = {"$or": query_conditions} if len(query_conditions) > 1 else query_conditions[0]
            companies = await db.companies.find(query).to_list(1000)
        else:
            companies = []
            
    elif current_user.role == "asesor":
        # Asesores can only see companies assigned to them
        companies = await db.companies.find({"asesor_comercial_id": current_user.id}).to_list(1000)
    else:
        # Staff can see all companies
        companies = await db.companies.find().to_list(1000)
    
    return [Company(**company) for company in companies]

@api_router.get("/companies/{company_id}", response_model=Company)
async def get_company(company_id: str, current_user: User = Depends(get_current_user)):
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check access permissions
    if current_user.role == "client":
        # Check if user has access through company_ids, company_id, or corporation
        has_access = (
            company_id in current_user.company_ids or
            company_id == current_user.company_id or
            (current_user.assigned_corporation and 
             company.get("corporacion") == current_user.assigned_corporation)
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return Company(**company)

@api_router.put("/companies/{company_id}", response_model=Company)
async def update_company(company_id: str, company_data: CompanyCreate, current_user: User = Depends(get_current_user)):
    # Only staff can update companies
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can update companies")
    
    # Check if company exists
    existing_company = await db.companies.find_one({"id": company_id})
    if not existing_company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Update company data
    update_data = company_data.dict(exclude_unset=True)
    
    result = await db.companies.update_one(
        {"id": company_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Return updated company
    updated_company = await db.companies.find_one({"id": company_id})
    return Company(**updated_company)

# Project management endpoints
@api_router.post("/projects", response_model=Project)
async def create_project(project_data: ProjectCreate, current_user: User = Depends(get_current_user)):
    # Verify company access
    if current_user.role == "client" and current_user.company_id != project_data.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    company = await db.companies.find_one({"id": project_data.company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Validate project_code uniqueness if provided
    if project_data.project_code:
        existing_project = await db.projects.find_one({
            "project_code": project_data.project_code,
            "company_id": project_data.company_id
        })
        if existing_project:
            raise HTTPException(
                status_code=400, 
                detail=f"Ya existe un proyecto con el ID '{project_data.project_code}' en esta empresa"
            )
    
    project_dict = project_data.dict()
    project_dict["created_by"] = current_user.id
    project = Project(**project_dict)
    
    await db.projects.insert_one(project.dict())
    return project

@api_router.get("/projects", response_model=List[Project])
async def get_projects(current_user: User = Depends(get_current_user)):
    if current_user.role == "client":
        # Get all companies the client has access to
        accessible_company_ids = set()
        
        # Add from company_ids list
        if current_user.company_ids:
            accessible_company_ids.update(current_user.company_ids)
        
        # Add backward compatibility for single company_id
        if current_user.company_id:
            accessible_company_ids.add(current_user.company_id)
        
        # Add companies from assigned corporation
        if current_user.assigned_corporation:
            corp_companies = await db.companies.find(
                {"corporacion": current_user.assigned_corporation}
            ).to_list(1000)
            accessible_company_ids.update([c["id"] for c in corp_companies])
        
        # Get projects from accessible companies
        if accessible_company_ids:
            projects = await db.projects.find(
                {"company_id": {"$in": list(accessible_company_ids)}}
            ).to_list(1000)
        else:
            projects = []
    else:
        # Staff and asesor can see all projects
        projects = await db.projects.find().to_list(1000)
    
    return [Project(**project) for project in projects]

@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, current_user: User = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access permissions for clients
    if current_user.role == "client":
        # Get company of this project
        project_company_id = project["company_id"]
        
        # Check if user has access
        has_access = (
            project_company_id in current_user.company_ids or
            project_company_id == current_user.company_id
        )
        
        # Check corporation access if not directly assigned
        if not has_access and current_user.assigned_corporation:
            company = await db.companies.find_one({"id": project_company_id})
            if company and company.get("corporacion") == current_user.assigned_corporation:
                has_access = True
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return Project(**project)

@api_router.get("/projects/{project_id}/documents", response_model=List[Document])
async def get_project_documents(project_id: str, current_user: User = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access permissions for clients
    if current_user.role == "client":
        # Get company of this project
        project_company_id = project["company_id"]
        
        # Check if user has access
        has_access = (
            project_company_id in current_user.company_ids or
            project_company_id == current_user.company_id
        )
        
        # Check corporation access if not directly assigned
        if not has_access and current_user.assigned_corporation:
            company = await db.companies.find_one({"id": project_company_id})
            if company and company.get("corporacion") == current_user.assigned_corporation:
                has_access = True
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get documents, ordered by display_order if available, then by created_at
    documents = await db.documents.find({"project_id": project_id}).to_list(1000)
    
    # Sort documents: first by display_order (if exists), then by created_at
    def sort_key(doc):
        display_order = doc.get("display_order")
        if display_order is not None:
            return (0, display_order)  # Ordered documents first
        else:
            return (1, doc.get("created_at", datetime.min))  # Unordered documents after
    
    documents.sort(key=sort_key)
    
    return [Document(**doc) for doc in documents]

# Document upload endpoint
@api_router.post("/projects/{project_id}/documents/upload", response_model=Document)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Check file size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo {file.filename} excede el límite de 500 MB. Tamaño: {file_size / (1024*1024):.2f} MB"
        )
    
    # Reset file pointer for saving
    await file.seek(0)
    
    # Save file
    file_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    filename = f"{file_id}{file_extension}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)
    
    # Create document record
    document = Document(
        filename=filename,
        original_filename=file.filename,
        project_id=project_id,
        file_path=str(file_path),
        uploaded_by=current_user.id
    )
    
    await db.documents.insert_one(document.dict())
    
    # Start QA processing first, then AI processing
    asyncio.create_task(process_document_qa_then_ai(document.id, project))
    
    return document

# Batch Upload Endpoint - Up to 10 PDFs simultaneously
@api_router.post("/projects/{project_id}/documents/batch-upload")
async def batch_upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Limit to 10 files maximum
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per batch")
    
    # Validate all files are PDFs and check sizes
    total_size = 0
    file_sizes = {}
    
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF. Only PDF files are supported")
        
        # Read file to check size
        content = await file.read()
        file_size = len(content)
        file_sizes[file.filename] = content
        
        # Check individual file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo {file.filename} excede el límite de 500 MB. Tamaño: {file_size / (1024*1024):.2f} MB"
            )
        
        total_size += file_size
        
        # Reset file pointer
        await file.seek(0)
    
    # Check total batch size
    if total_size > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"El tamaño total del lote excede 1 GB. Tamaño total: {total_size / (1024*1024*1024):.2f} GB. Por favor, suba los archivos en múltiples lotes."
        )
    
    document_ids = []
    
    # Save all files first
    for file in files:
        # Save file
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        filename = f"{file_id}{file_extension}"
        file_path = UPLOAD_DIR / filename
        
        # Use the already-read content
        with open(file_path, "wb") as buffer:
            buffer.write(file_sizes[file.filename])
        
        # Create document record
        document = Document(
            filename=filename,
            original_filename=file.filename,
            project_id=project_id,
            file_path=str(file_path),
            status="pending",  # Start as pending for batch processing
            uploaded_by=current_user.id
        )
        
        await db.documents.insert_one(document.dict())
        document_ids.append(document.id)
    
    # Create batch processing task
    batch_task = BatchProcessTask(
        project_id=project_id,
        document_ids=document_ids
    )
    
    await db.batch_tasks.insert_one(batch_task.dict())
    
    # Start batch processing in background
    background_tasks.add_task(process_documents_batch, batch_task.id, project)
    
    return {
        "message": f"Batch upload successful. {len(files)} documents uploaded. Total size: {total_size / (1024*1024):.2f} MB",
        "batch_task_id": batch_task.id,
        "document_ids": document_ids,
        "files_uploaded": len(files),
        "total_size_mb": round(total_size / (1024*1024), 2)
    }


@api_router.post("/projects/{project_id}/documents/{document_id}/qa-review")
async def update_qa_review(
    project_id: str,
    document_id: str,
    review_data: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Update QA review with comments and action (approve/reject).
    Only staff can perform QA review.
    """
    try:
        # Only staff can review QA
        if current_user.role != "staff":
            raise HTTPException(status_code=403, detail="Solo el staff puede revisar documentos QA")
        
        # Find document
        document = await db.documents.find_one({"id": document_id, "project_id": project_id})
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        # Validate action
        action = review_data.get("action")  # "approved" or "rejected"
        if action not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="Acción inválida. Debe ser 'approved' o 'rejected'")
        
        comments = review_data.get("comments", "")
        
        # Update document with review information
        update_data = {
            "qa_review_action": action,
            "qa_review_comments": comments,
            "qa_approved_by": current_user.id,
            "qa_reviewed_by_name": current_user.name,
            "qa_approved_at": datetime.now(timezone.utc)
        }
        
        # Update status based on action
        if action == "approved":
            update_data["status"] = "qa_passed"
            update_data["qa_status"] = "passed"
            # Continue to AI processing - get project first
            project = await db.projects.find_one({"id": project_id})
            if project:
                asyncio.create_task(process_document_with_ai(document_id, project))
        else:  # rejected
            update_data["status"] = "qa_failed"
            update_data["qa_status"] = "failed"
        
        await db.documents.update_one(
            {"id": document_id},
            {"$set": update_data}
        )
        
        logger.info(f"QA review completed for document {document_id} by {current_user.email}: {action}")
        
        return {
            "message": f"Documento {'aprobado' if action == 'approved' else 'rechazado'} exitosamente",
            "document_id": document_id,
            "action": action,
            "reviewed_by": current_user.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating QA review: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Batch Processing Status Endpoint
@api_router.get("/projects/{project_id}/batch-status/{batch_task_id}")
async def get_batch_processing_status(
    project_id: str,
    batch_task_id: str,
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get batch task
    batch_task = await db.batch_tasks.find_one({"id": batch_task_id})
    if not batch_task:
        raise HTTPException(status_code=404, detail="Batch task not found")
    
    # Get current document statuses
    documents = await db.documents.find(
        {"id": {"$in": batch_task["document_ids"]}}
    ).to_list(length=None)
    
    document_statuses = []
    for doc in documents:
        document_statuses.append({
            "id": doc["id"],
            "filename": doc["original_filename"],
            "status": doc["status"],
            "processed_at": doc.get("processed_at")
        })
    
    return {
        "batch_task_id": batch_task_id,
        "status": batch_task["status"],
        "progress": batch_task["progress"],
        "completed_documents": batch_task["completed_documents"],
        "failed_documents": batch_task["failed_documents"],
        "total_documents": len(batch_task["document_ids"]),
        "document_statuses": document_statuses,
        "created_at": batch_task["created_at"],
        "started_at": batch_task.get("started_at"),
        "completed_at": batch_task.get("completed_at")
    }

# Batch Processing Function
async def process_documents_batch(batch_task_id: str, project: dict):
    """Process multiple documents in parallel with a limit of 10 concurrent tasks"""
    try:
        # Update batch task status
        await db.batch_tasks.update_one(
            {"id": batch_task_id},
            {
                "$set": {
                    "status": "processing",
                    "started_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Get batch task details
        batch_task = await db.batch_tasks.find_one({"id": batch_task_id})
        if not batch_task:
            return
        
        document_ids = batch_task["document_ids"]
        total_documents = len(document_ids)
        completed_documents = 0
        failed_documents = 0
        
        # Dynamic concurrency based on document count for better performance
        def get_optimal_concurrency(document_count):
            """Determine optimal concurrency for processing efficiency"""
            if document_count <= 5:
                return document_count  # Process all small batches simultaneously
            elif document_count <= 20:
                return 10          # Standard concurrency for medium batches
            elif document_count <= 100:
                return 15          # Higher concurrency for large documents
            else:
                return 20          # Maximum concurrency for massive documents
        
        max_concurrency = get_optimal_concurrency(total_documents)
        semaphore = asyncio.Semaphore(max_concurrency)
        
        logger.info(f"Processing with {max_concurrency} concurrent documents for optimal throughput")
        
        async def process_single_document(doc_id):
            nonlocal completed_documents, failed_documents
            
            async with semaphore:
                try:
                    await process_document_with_ai(doc_id, project)
                    
                    # Check if processing was successful
                    doc = await db.documents.find_one({"id": doc_id})
                    if doc and doc["status"] == "completed":
                        completed_documents += 1
                    else:
                        failed_documents += 1
                        
                except Exception as e:
                    logger.error(f"Error processing document {doc_id}: {str(e)}")
                    failed_documents += 1
                    await db.documents.update_one(
                        {"id": doc_id},
                        {"$set": {"status": "failed"}}
                    )
                
                # Update batch progress
                progress = int(((completed_documents + failed_documents) / total_documents) * 100)
                await db.batch_tasks.update_one(
                    {"id": batch_task_id},
                    {
                        "$set": {
                            "progress": progress,
                            "completed_documents": completed_documents,
                            "failed_documents": failed_documents
                        }
                    }
                )
        
        # Process all documents in parallel
        tasks = [process_single_document(doc_id) for doc_id in document_ids]
        await asyncio.gather(*tasks)
        
        # Update batch task as completed
        await db.batch_tasks.update_one(
            {"id": batch_task_id},
            {
                "$set": {
                    "status": "completed",
                    "progress": 100,
                    "completed_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"Batch processing completed: {completed_documents} successful, {failed_documents} failed")
        
    except Exception as e:
        logger.error(f"Error in batch processing {batch_task_id}: {str(e)}")
        await db.batch_tasks.update_one(
            {"id": batch_task_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc)
                }
            }
        )

# PDF Chunking Helper Functions
def get_pdf_page_count(file_path: str) -> int:
    """Get total number of pages in PDF"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            return len(pdf_reader.pages)
    except Exception as e:
        logger.error(f"Error getting PDF page count: {str(e)}")
        return 0

def create_pdf_chunk(source_path: str, start_page: int, end_page: int, output_path: str) -> bool:
    """Create a PDF chunk from specific pages"""
    try:
        import PyPDF2
        with open(source_path, 'rb') as source_file:
            pdf_reader = PyPDF2.PdfReader(source_file)
            pdf_writer = PyPDF2.PdfWriter()
            
            # Add pages to the new PDF
            for page_num in range(start_page, min(end_page + 1, len(pdf_reader.pages))):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Write the chunk PDF
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            return True
    except Exception as e:
        logger.error(f"Error creating PDF chunk: {str(e)}")
        return False

async def extract_text_with_gpt4o_vision(file_path: str, start_page: int, end_page: int, project_id: str, document_id: Optional[str] = None) -> str:
    """
    Extract text from PDF pages using GPT-4o Vision.
    Converts pages to images and uses Vision API to read text.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        from pdf2image import convert_from_path
        import base64
        from io import BytesIO
        
        logger.info(f"Using GPT-4o Vision OCR for pages {start_page + 1} to {end_page + 1}")
        
        # Get AI configuration for the project
        ai_config = await get_ai_config_for_task(project_id, "data_extraction")
        if not ai_config or not ai_config.get("api_key"):
            logger.error("No AI configuration available for GPT-4o Vision OCR")
            return "[Error: No AI configuration available for Vision OCR]"
        
        # Convert PDF pages to images
        images = convert_from_path(
            file_path,
            first_page=start_page + 1,  # pdf2image uses 1-indexed pages
            last_page=end_page + 1,
            dpi=150  # Lower DPI for faster processing
        )
        
        total_pages = len(images)
        logger.info(f"Converted {total_pages} pages to images for Vision OCR")
        
        # Process each page with GPT-4o Vision
        pdf_text = ""
        
        for idx, image in enumerate(images):
            actual_page_num = start_page + idx
            
            # Update progress every 2 pages
            if document_id and idx % 2 == 0:
                progress_pct = int((idx / total_pages) * 100)
                await db.documents.update_one(
                    {"id": document_id},
                    {"$set": {
                        "processing_message": f"🔍 GPT-4o Vision: Procesando página {idx + 1}/{total_pages}... ({progress_pct}%)"
                    }}
                )
            
            try:
                # Convert PIL Image to base64
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                
                # Create chat instance
                chat = await create_ai_chat_with_config(
                    ai_config,
                    f"vision_ocr_page_{actual_page_num}",
                    "You are an expert OCR assistant. Extract all visible text from images accurately."
                )
                
                # Create image content
                image_content = ImageContent(image_base64=img_base64)
                
                # Create user message with image
                user_message = UserMessage(
                    text="Extract all text from this document image. Return ONLY the text content, maintaining the original layout and structure as much as possible. Do not add any explanations or comments.",
                    file_contents=[image_content]
                )
                
                # Send message and get response
                response = await chat.send_message(user_message)
                
                pdf_text += f"\n--- PAGE {actual_page_num + 1} ---\n"
                pdf_text += response.strip()
                
                logger.info(f"Vision OCR Page {actual_page_num + 1}: Extracted {len(response)} characters")
                
            except Exception as page_error:
                logger.error(f"Vision OCR failed for page {actual_page_num + 1}: {str(page_error)}")
                pdf_text += f"\n--- PAGE {actual_page_num + 1} ---\n"
                pdf_text += f"[Vision OCR Error: {str(page_error)}]\n"
        
        return pdf_text
        
    except Exception as e:
        logger.error(f"GPT-4o Vision OCR processing failed: {str(e)}", exc_info=True)
        return f"[Vision OCR Error: {str(e)}]"

async def extract_text_from_pdf_with_ocr(
    file_path: str, 
    project_id: str,
    start_page: int = 0, 
    end_page: int = None, 
    max_pages: int = None,
    document_id: Optional[str] = None  # For progress updates
) -> str:
    """
    Extract text from PDF with OCR fallback for scanned documents.
    Uses global OCR configuration to determine method (tesseract or gpt4o_vision).
    Only applies OCR if PyPDF2 fails to extract text.
    
    Args:
        file_path: Path to PDF file
        project_id: Project ID for AI configuration (needed for Vision OCR)
        start_page: Starting page (0-indexed)
        end_page: Ending page (0-indexed, inclusive). If None, extracts to end
        max_pages: Maximum number of pages to extract. If None, no limit
        document_id: Document ID for progress updates (optional)
    
    Returns:
        Extracted text as string
    """
    import PyPDF2
    
    pdf_text = ""
    total_text_length = 0
    
    try:
        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pdf_pages = len(pdf_reader.pages)
            
            # Determine actual end page
            if end_page is None:
                end_page = total_pdf_pages - 1
            else:
                end_page = min(end_page, total_pdf_pages - 1)
            
            # Apply max_pages limit if specified
            if max_pages is not None:
                end_page = min(start_page + max_pages - 1, end_page)
            
            # First attempt: Extract text using PyPDF2
            if document_id:
                await db.documents.update_one(
                    {"id": document_id},
                    {"$set": {"processing_message": "Intentando extraer texto del PDF..."}}
                )
            pages_processed = 0
            for page_num in range(start_page, end_page + 1):
                page = pdf_reader.pages[page_num]
                pdf_text += f"\n--- PAGE {page_num + 1} ---\n"
                page_text = page.extract_text()
                pdf_text += page_text
                total_text_length += len(page_text.strip())
                pages_processed += 1
            
            logger.info(f"PyPDF2 extracted {total_text_length} characters from {pages_processed} pages")
            
            # If minimal text was extracted, check if OCR is enabled
            if total_text_length < 50 and pages_processed > 0:
                logger.info(f"Minimal text extracted ({total_text_length} chars). Checking OCR configuration...")
                
                # Get global OCR configuration
                ocr_config = await db.ocr_config.find_one({"id": "global_ocr_config"})
                ocr_enabled = ocr_config.get("ocr_enabled", False) if ocr_config else False
                ocr_method = ocr_config.get("ocr_method", "gpt4o_vision") if ocr_config else "gpt4o_vision"
                
                if not ocr_enabled:
                    logger.warning("OCR is disabled. Document has no text and OCR is turned off.")
                    if document_id:
                        await db.documents.update_one(
                            {"id": document_id},
                            {"$set": {"processing_message": "⚠️ PDF sin texto detectado. OCR está deshabilitado en configuración."}}
                        )
                    pdf_text += "\n\n[ADVERTENCIA: Este PDF no contiene texto incrustado y el OCR está deshabilitado en la configuración global. Habilita OCR en 'Configuración IA' para procesar documentos escaneados.]\n"
                else:
                    logger.info(f"OCR enabled. Using method: {ocr_method}")
                    
                    if ocr_method == "gpt4o_vision":
                        # Use GPT-4o Vision for OCR
                        logger.info("Attempting GPT-4o Vision OCR...")
                        if document_id:
                            await db.documents.update_one(
                                {"id": document_id},
                                {"$set": {"processing_message": f"🔍 Iniciando GPT-4o Vision OCR ({pages_processed} páginas)..."}}
                            )
                        pdf_text = await extract_text_with_gpt4o_vision(
                            file_path, 
                            start_page, 
                            end_page, 
                            project_id,
                            document_id
                        )
                        
                    elif ocr_method == "tesseract":
                        # Use Tesseract OCR
                        logger.info("Attempting Tesseract OCR...")
                        if document_id:
                            await db.documents.update_one(
                                {"id": document_id},
                                {"$set": {"processing_message": f"🔍 Extrayendo texto con Tesseract OCR ({pages_processed} páginas)..."}}
                            )
                        try:
                            import pytesseract
                            from pdf2image import convert_from_path
                            
                            # Convert PDF pages to images
                            images = convert_from_path(
                                file_path,
                                first_page=start_page + 1,  # pdf2image uses 1-indexed pages
                                last_page=end_page + 1,
                                dpi=200
                            )
                            
                            # Perform OCR on each page
                            pdf_text = ""  # Reset text
                            ocr_success_count = 0
                            total_images = len(images)
                            
                            for idx, image in enumerate(images):
                                actual_page_num = start_page + idx
                                
                                # Update progress every 3 pages
                                if document_id and idx > 0 and idx % 3 == 0:
                                    progress_pct = int((idx / total_images) * 100)
                                    await db.documents.update_one(
                                        {"id": document_id},
                                        {"$set": {
                                            "processing_message": f"🔍 Tesseract OCR: Procesando página {idx + 1}/{total_images}... ({progress_pct}%)"
                                        }}
                                    )
                                
                                try:
                                    ocr_text = pytesseract.image_to_string(
                                        image,
                                        lang='spa',
                                        config='--psm 6'
                                    ).strip()
                                    
                                    pdf_text += f"\n--- PAGE {actual_page_num + 1} ---\n"
                                    pdf_text += ocr_text
                                    
                                    if ocr_text and len(ocr_text) > 20:
                                        ocr_success_count += 1
                                        logger.info(f"Tesseract OCR Page {actual_page_num + 1}: Extracted {len(ocr_text)} characters")
                                    else:
                                        logger.warning(f"Tesseract OCR Page {actual_page_num + 1}: Minimal text extracted")
                                        
                                except Exception as page_ocr_error:
                                    logger.error(f"Tesseract OCR failed for page {actual_page_num + 1}: {str(page_ocr_error)}")
                                    pdf_text += f"\n[OCR Error on page {actual_page_num + 1}]\n"
                            
                            logger.info(f"Tesseract OCR completed: {ocr_success_count}/{pages_processed} pages processed successfully")
                            
                        except ImportError as import_error:
                            logger.error(f"Tesseract OCR libraries not available: {str(import_error)}")
                            pdf_text += "\n[Tesseract OCR not available - please install pytesseract and pdf2image]\n"
                        except Exception as ocr_error:
                            logger.error(f"Tesseract OCR processing failed: {str(ocr_error)}", exc_info=True)
                            pdf_text += "\n[Tesseract OCR processing failed]\n"
            
            # Add note if pages were truncated
            if end_page < total_pdf_pages - 1:
                pdf_text += f"\n\n[Note: Document has {total_pdf_pages} total pages, extracted pages {start_page + 1} to {end_page + 1}]"
                    
    except Exception as e:
        logger.error(f"Error extracting PDF text: {str(e)}", exc_info=True)
        pdf_text = f"[Error: Could not extract text from PDF - {str(e)}]"
    
    return pdf_text

# QA Processing Functions
async def process_document_qa_then_ai(document_id: str, project: dict):
    """Process document with QA first, then AI extraction if QA passes"""
    try:
        # Get document
        document = await db.documents.find_one({"id": document_id})
        if not document:
            return
        
        logger.info(f"Starting QA processing for document {document_id}")
        
        # Update document status to QA pending
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"status": "qa_pending", "qa_status": "pending"}}
        )
        
        # Get applicable QA agents for this project
        qa_agents = await get_applicable_qa_agents(project["id"])
        
        if not qa_agents:
            # No QA agents configured, proceed directly to AI processing
            logger.info(f"No QA agents found for project {project['id']}, proceeding to AI processing")
            await db.documents.update_one(
                {"id": document_id},
                {"$set": {"status": "processing", "qa_status": "skipped"}}
            )
            await process_document_with_ai(document_id, project)
            return
        
        # Run QA checks
        qa_results = await run_qa_checks(document_id, document, qa_agents)
        
        # Determine QA outcome
        overall_score = qa_results.get("overall_score", 0)
        critical_findings = qa_results.get("critical_findings", [])
        
        if overall_score < 60:  # Failed QA
            await db.documents.update_one(
                {"id": document_id},
                {
                    "$set": {
                        "status": "qa_failed",
                        "qa_status": "failed",
                        "qa_results": qa_results,
                        "qa_findings": critical_findings,
                        "qa_processed_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"Document {document_id} failed QA with score {overall_score}")
        
        elif overall_score < 80 or len(critical_findings) > 0:  # Needs manual review
            await db.documents.update_one(
                {"id": document_id},
                {
                    "$set": {
                        "status": "needs_review",
                        "qa_status": "manual_review",
                        "qa_results": qa_results,
                        "qa_findings": critical_findings,
                        "qa_processed_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"Document {document_id} needs manual review - score: {overall_score}, findings: {len(critical_findings)}")
        
        else:  # Passed QA, proceed to AI processing
            await db.documents.update_one(
                {"id": document_id},
                {
                    "$set": {
                        "status": "processing",
                        "qa_status": "passed",
                        "qa_results": qa_results,
                        "qa_processed_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"Document {document_id} passed QA with score {overall_score}, proceeding to AI processing")
            await process_document_with_ai(document_id, project)
        
    except Exception as e:
        logger.error(f"Error in QA processing for document {document_id}: {str(e)}")
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "qa_failed",
                    "qa_status": "error",
                    "qa_results": {"error": str(e)},
                    "qa_processed_at": datetime.now(timezone.utc)
                }
            }
        )

async def get_applicable_qa_agents(project_id: str) -> list:
    """Get QA agents applicable to a project"""
    try:
        # Get universal agents and project-specific agents
        agents = await db.qa_agents.find({
            "$or": [
                {"is_universal": True, "is_active": True, "auto_process": True},
                {"project_ids": {"$in": [project_id]}, "is_active": True, "auto_process": True}
            ]
        }).to_list(1000)
        
        return agents
    except Exception as e:
        logger.error(f"Error getting QA agents for project {project_id}: {str(e)}")
        return []

async def run_qa_checks(document_id: str, document: dict, qa_agents: list) -> dict:
    """Run QA checks on document using specified agents"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
        
        # Update progress
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {
                "processing_message": f"✅ Iniciando controles de calidad con {len(qa_agents)} agentes..."
            }}
        )
        
        # Get AI configuration for QA
        project = await db.projects.find_one({"id": document["project_id"]})
        company = await db.companies.find_one({"id": project["company_id"]})
        
        ai_config = await get_ai_config_for_task(document["project_id"], "qa_processing")
        if not ai_config.get("api_key"):
            return {"error": "No AI configuration available", "overall_score": 0}
        
        # Extract text from PDF for analysis with OCR fallback
        # Note: emergentintegrations only supports file attachments with Gemini provider
        # For OpenAI, we extract text and send it in the prompt
        pdf_text = await extract_text_from_pdf_with_ocr(
            document["file_path"],
            project_id=document["project_id"],
            start_page=0,
            max_pages=3,  # Extract first 3 pages for QA (reduced for Vision OCR performance)
            document_id=document_id  # Pass document_id for OCR progress messages
        )
        
        all_results = []
        critical_findings = []
        
        for idx, agent in enumerate(qa_agents):
            try:
                # Update progress
                await db.documents.update_one(
                    {"id": document_id},
                    {"$set": {
                        "processing_message": f"✅ Ejecutando agente QA {idx + 1}/{len(qa_agents)}: {agent.get('name', 'Agente')}..."
                    }}
                )
                
                # Create AI chat for QA using configured model
                chat = await create_ai_chat_with_config(
                    ai_config,
                    f"qa_{agent['id']}_{document_id}",
                    "Eres un asistente de control de calidad de documentos con IA. Analiza documentos en busca de problemas de calidad y proporciona una evaluación detallada en español."
                )
                
                # Create QA prompt
                quality_checks = agent.get("quality_checks", {})
                active_checks = [check for check, enabled in quality_checks.items() if enabled]
                
                prompt = f"""
                Analiza este documento para control de calidad basándote en los siguientes criterios:
                
                INSTRUCCIONES DE QA: {agent['qa_instructions']}
                
                VERIFICACIONES DE CALIDAD A REALIZAR:
                {', '.join(active_checks) if active_checks else 'Evaluación general de calidad del documento'}
                
                CONTENIDO DE TEXTO DEL DOCUMENTO:
                {pdf_text[:15000]}
                
                Por favor proporciona una respuesta en JSON con:
                {{
                    "overall_score": <0-100>,
                    "quality_assessment": {{
                        "text_readability": <0-100>,
                        "completeness": <0-100>,
                        "structure": <0-100>,
                        "content_quality": <0-100>
                    }},
                    "findings": [
                        {{
                            "type": "critical|warning|info",
                            "category": "legibilidad|completitud|estructura|contenido|otro",
                            "description": "Descripción detallada en español",
                            "location": "número de página o sección",
                            "recommendation": "Cómo corregirlo"
                        }}
                    ],
                    "recommendation": "approve|manual_review|reject",
                    "summary": "Resumen breve de la evaluación en español"
                }}
                
                Puntuación 0-100 donde:
                - 80-100: Excelente calidad, aprobar automáticamente
                - 60-79: Buena calidad pero puede necesitar revisión
                - 0-59: Calidad deficiente, probablemente necesita rechazo o reprocesamiento
                
                Nota: Las verificaciones de calidad visual (claridad de imagen, orientación) requieren análisis visual que no está disponible con procesamiento solo de texto.
                Enfócate en la legibilidad del texto, completitud, estructura y calidad del contenido.
                
                IMPORTANTE: Todas las descripciones, recomendaciones y resúmenes deben estar en español.
                """
                
                user_message = UserMessage(text=prompt)
                
                # Get AI response
                response = await chat.send_message(user_message)
                
                # Parse AI response
                import json
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                
                if json_match:
                    try:
                        qa_result = json.loads(json_match.group())
                        qa_result["agent_id"] = agent["id"]
                        qa_result["agent_name"] = agent["name"]
                        all_results.append(qa_result)
                        
                        # Collect critical findings
                        findings = qa_result.get("findings", [])
                        for finding in findings:
                            if finding.get("type") == "critical":
                                critical_findings.append({
                                    "agent": agent["name"],
                                    "finding": finding,
                                    "document_id": document_id
                                })
                                
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse QA response for agent {agent['id']}")
                        all_results.append({
                            "agent_id": agent["id"],
                            "agent_name": agent["name"],
                            "error": "Failed to parse response",
                            "overall_score": 50,
                            "raw_response": response
                        })
                        
            except Exception as e:
                logger.error(f"Error running QA agent {agent['id']}: {str(e)}")
                all_results.append({
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "error": str(e),
                    "overall_score": 0
                })
        
        # Calculate overall score (average of all agent scores)
        scores = [result.get("overall_score", 0) for result in all_results if "overall_score" in result]
        overall_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "overall_score": overall_score,
            "agent_results": all_results,
            "critical_findings": critical_findings,
            "qa_summary": f"Processed by {len(qa_agents)} QA agents with average score {overall_score:.1f}"
        }
        
    except Exception as e:
        logger.error(f"Error in QA checks for document {document_id}: {str(e)}")
        return {
            "error": str(e),
            "overall_score": 0,
            "critical_findings": []
        }

async def get_ai_config_for_task(project_id: str, task_type: str) -> dict:
    """Get AI configuration for a specific task type"""
    try:
        logger.info(f"Getting AI config for project {project_id}, task type: {task_type}")
        
        # Look for project-specific configuration
        config = await db.ai_configurations.find_one({
            "project_id": project_id,
            "config_type": task_type,
            "is_active": True
        })
        
        if config and config.get("api_key"):
            logger.info(f"Found project-specific AI config for {project_id}, provider: {config['provider']}, model: {config['model_name']}")
            # Decrypt API key
            try:
                decrypted_key = decrypt_api_key(config["api_key"])
                logger.info(f"Successfully decrypted API key for project {project_id}")
                
                # Validate decrypted key
                if not decrypted_key or len(decrypted_key) < 10:
                    raise ValueError("Decrypted API key is invalid or too short")
                
                return {
                    "provider": config["provider"],
                    "api_key": decrypted_key,
                    "model_name": config["model_name"],
                    "model_config": config.get("model_parameters", {}),
                    "source": "project_config"
                }
            except Exception as e:
                logger.error(f"Failed to decrypt API key for project {project_id}: {str(e)}", exc_info=True)
                logger.warning(f"Falling back to Emergent LLM key due to decryption error")
        else:
            logger.info(f"No project-specific AI config found for {project_id}, using fallback")
        
        # Fallback to Emergent LLM key with recommended models
        fallback_models = {
            "data_extraction": "gpt-4o",
            "qa_processing": "gpt-4o-mini", 
            "document_processing": "gpt-4o"
        }
        
        emergent_key = os.environ.get('EMERGENT_LLM_KEY')
        logger.info(f"Using Emergent LLM key fallback with model: {fallback_models.get(task_type, 'gpt-4o')}")
        
        return {
            "provider": "emergent",
            "api_key": emergent_key,
            "model_name": fallback_models.get(task_type, "gpt-4o"),
            "model_config": {},
            "source": "fallback_emergent"
        }
        
    except Exception as e:
        logger.error(f"Error getting AI config for project {project_id}, task {task_type}: {str(e)}", exc_info=True)
        return {
            "provider": "emergent",
            "api_key": os.environ.get('EMERGENT_LLM_KEY'),
            "model_name": "gpt-4o",
            "model_config": {},
            "source": "error_fallback"
        }

async def create_ai_chat_with_config(config: dict, session_id: str, system_message: str):
    """Create AI chat instance with configuration"""
    try:
        from emergentintegrations.llm.chat import LlmChat
        
        logger.info(f"Creating AI chat with provider: {config['provider']}, model: {config['model_name']}, source: {config.get('source', 'unknown')}")
        
        # Validate API key
        if not config.get("api_key"):
            raise ValueError("API key is missing from configuration")
        
        # Log API key info (first 10 chars for debugging, never log full key)
        key_preview = config["api_key"][:10] + "..." if len(config["api_key"]) > 10 else "short_key"
        logger.info(f"Using API key starting with: {key_preview}")
        
        if config["provider"] == "openai":
            # Use OpenAI directly with customer's API key
            logger.info("Initializing LlmChat with customer's OpenAI API key")
            chat = LlmChat(
                api_key=config["api_key"],
                session_id=session_id,
                system_message=system_message
            ).with_model("openai", config["model_name"])
        else:
            # Use Emergent integration
            logger.info("Initializing LlmChat with Emergent LLM key")
            chat = LlmChat(
                api_key=config["api_key"],
                session_id=session_id,
                system_message=system_message
            ).with_model("openai", config["model_name"])  # Emergent handles OpenAI models
        
        logger.info(f"AI chat created successfully with session_id: {session_id}")
        return chat
        
    except Exception as e:
        logger.error(f"Failed to create AI chat: {str(e)}", exc_info=True)
        raise

async def store_extracted_data_normalized(document_id: str, document: dict, project: dict, extracted_data: dict):
    """Store extracted data in normalized format for efficient querying by client"""
    try:
        # Get project and company info
        company = await db.companies.find_one({"id": project["company_id"]})
        if not company:
            logger.error(f"Company not found for project {project['id']}")
            return
        
        # Extract the actual data (skip metadata)
        actual_data = extracted_data.get("extracted_data", extracted_data)
        if isinstance(actual_data, dict):
            
            # Store individual fields
            extracted_records = []
            for field_name, field_value in actual_data.items():
                if field_name not in ["status", "chunk_processing", "page_ranges"]:  # Skip metadata
                    
                    # Handle different data types
                    if isinstance(field_value, (list, dict)):
                        field_value_str = json.dumps(field_value, ensure_ascii=False)
                        field_type = "json"
                    elif isinstance(field_value, (int, float)):
                        field_value_str = str(field_value)
                        field_type = "number"
                    else:
                        field_value_str = str(field_value)
                        field_type = "text"
                    
                    # Determine confidence (if available from chunk processing)
                    confidence = None
                    if "chunk_processing" in extracted_data:
                        successful_chunks = extracted_data["chunk_processing"].get("successful_chunks", 0)
                        total_chunks = extracted_data["chunk_processing"].get("total_chunks", 1)
                        confidence = successful_chunks / total_chunks if total_chunks > 0 else 0.5
                    
                    extracted_record = ExtractedData(
                        company_id=company["id"],
                        project_id=project["id"],
                        document_id=document_id,
                        document_name=document["original_filename"],
                        field_name=field_name,
                        field_value=field_value_str,
                        field_type=field_type,
                        confidence=confidence,
                        processing_method="ai_extraction"
                    )
                    
                    extracted_records.append(extracted_record.dict())
            
            # Bulk insert extracted data
            if extracted_records:
                await db.extracted_data.insert_many(extracted_records)
                logger.info(f"Stored {len(extracted_records)} extracted fields for document {document_id}")
            
            # Store document summary
            summary = ExtractedDataSummary(
                company_id=company["id"],
                project_id=project["id"],
                document_id=document_id,
                summary_data=actual_data,
                total_fields=len(extracted_records)
            )
            
            await db.extracted_data_summaries.insert_one(summary.dict())
            
    except Exception as e:
        logger.error(f"Error storing normalized extracted data for document {document_id}: {str(e)}")

async def process_single_chunk(file_path: str, semantic_instructions: str, ai_config: dict, chunk_number: int, start_page: int, end_page: int, project_id: str, original_start: int = None, original_end: int = None) -> dict:
    """
    Process a single PDF chunk with AI using configured model
    
    Args:
        file_path: Path to the chunk PDF file
        semantic_instructions: Instructions for data extraction
        ai_config: AI configuration
        chunk_number: Chunk number for tracking
        start_page: Start page within the chunk PDF (1-indexed)
        end_page: End page within the chunk PDF (1-indexed)
        project_id: Project ID
        original_start: Original start page in the full document (for display)
        original_end: Original end page in the full document (for display)
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        # Use original page numbers for display if provided
        display_start = original_start if original_start else start_page
        display_end = original_end if original_end else end_page
        
        # Extract text from specified pages of the PDF with OCR fallback
        # Note: emergentintegrations only supports file attachments with Gemini provider
        # For OpenAI, we extract text and send it in the prompt
        pdf_text = await extract_text_from_pdf_with_ocr(
            file_path,
            project_id=project_id,
            start_page=start_page - 1,  # Convert to 0-indexed
            end_page=end_page - 1  # Convert to 0-indexed
        )
        
        chat = await create_ai_chat_with_config(
            ai_config,
            f"chunk_processing_{chunk_number}_{start_page}_{end_page}",
            "You are an expert document analysis AI. Extract structured data from document chunks based on specific instructions."
        )
        
        prompt = f"""
        CRITICAL INSTRUCTIONS - READ CAREFULLY:
        
        You are processing pages {display_start} to {display_end} of a legal/insurance document.
        
        EXTRACTION RULES:
        1. Extract ONLY REAL DATA that is ACTUALLY PRESENT in the document text below
        2. DO NOT generate examples, fictitious data, or placeholder information
        3. DO NOT invent names, numbers, dates, addresses, or any information
        4. If a field is not found in the text, use null (not "N/A" or empty string)
        5. Maintain original spelling, capitalization, and formatting from the document
        
        EXTRACTION INSTRUCTIONS:
        {semantic_instructions}
        
        DOCUMENT TEXT CONTENT (Pages {display_start} to {display_end}):
        ===START OF DOCUMENT TEXT===
        {pdf_text}
        ===END OF DOCUMENT TEXT===
        
        RESPONSE FORMAT - EXTREMELY IMPORTANT:
        You MUST respond with ONLY a JSON object. Do not include any explanatory text, markdown, or formatting.
        Start your response with {{ and end with }}.
        
        Example of correct response format:
        {{
          "field_name": "actual value from document",
          "another_field": "another actual value",
          "not_found_field": null
        }}
        
        DO NOT write anything like "Here is the extracted data:" or "```json" - just the JSON object itself.
        
        This is chunk {chunk_number} of a larger document. Extract all relevant data from these specific pages.
        
        RESPOND NOW WITH ONLY THE JSON OBJECT:
        """
        
        user_message = UserMessage(text=prompt)
        
        # Process with AI
        response = await chat.send_message(user_message)
        
        # Log response for debugging
        logger.info(f"Chunk {chunk_number} AI response length: {len(response)} characters")
        logger.debug(f"Chunk {chunk_number} AI response preview: {response[:500]}...")
        
        # Try to parse JSON from response
        import json
        import re
        
        # Try multiple strategies to extract JSON
        extracted_data = None
        
        # Strategy 1: Look for JSON between ```json and ``` markers
        json_code_block = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
        if json_code_block:
            try:
                extracted_data = json.loads(json_code_block.group(1))
                logger.info(f"Chunk {chunk_number}: Extracted JSON from code block")
            except json.JSONDecodeError as e:
                logger.warning(f"Chunk {chunk_number}: Failed to parse JSON from code block: {e}")
        
        # Strategy 2: Look for JSON between curly braces (greedy match for nested objects)
        if not extracted_data:
            # Find the outermost JSON object
            brace_count = 0
            start_idx = -1
            end_idx = -1
            
            for i, char in enumerate(response):
                if char == '{':
                    if brace_count == 0:
                        start_idx = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_idx != -1:
                        end_idx = i + 1
                        break
            
            if start_idx != -1 and end_idx != -1:
                try:
                    json_str = response[start_idx:end_idx]
                    extracted_data = json.loads(json_str)
                    logger.info(f"Chunk {chunk_number}: Extracted JSON using brace matching")
                except json.JSONDecodeError as e:
                    logger.warning(f"Chunk {chunk_number}: Failed to parse JSON with brace matching: {e}")
        
        # If we successfully extracted data, return success
        if extracted_data:
            return {
                "chunk_number": chunk_number,
                "start_page": display_start,
                "end_page": display_end,
                "data": extracted_data,
                "status": "success"
            }
        else:
            # No valid JSON found
            logger.warning(f"Chunk {chunk_number}: No valid JSON found in AI response")
            return {
                "chunk_number": chunk_number,
                "start_page": display_start,
                "end_page": display_end,
                "raw_response": response[:1000],  # Store first 1000 chars for review
                "status": "needs_review",
                "error": "No valid JSON structure found in AI response"
            }
            
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_number}: {str(e)}")
        return {
            "chunk_number": chunk_number,
            "start_page": display_start if original_start else start_page,
            "end_page": display_end if original_end else end_page,
            "error": str(e),
            "status": "failed"
        }

def combine_chunk_results(chunk_results: list) -> dict:
    """Combine results from multiple chunks into a single document result - Optimized for large documents"""
    try:
        if not chunk_results:
            return {"error": "No chunks processed", "status": "failed"}
        
        successful_chunks = [c for c in chunk_results if c.get("status") == "success"]
        failed_chunks = [c for c in chunk_results if c.get("status") == "failed"]
        
        # For large documents, store only essential chunk info to save memory
        chunk_summaries = []
        for chunk in chunk_results:
            chunk_summary = {
                "chunk_number": chunk.get("chunk_number"),
                "pages": f"{chunk.get('start_page')}-{chunk.get('end_page')}",
                "status": chunk.get("status"),
                "data_keys": list(chunk.get("data", {}).keys()) if chunk.get("data") else []
            }
            chunk_summaries.append(chunk_summary)
        
        combined_data = {
            "chunk_processing": {
                "total_chunks": len(chunk_results),
                "successful_chunks": len(successful_chunks),
                "failed_chunks": len(failed_chunks),
                "success_rate": f"{(len(successful_chunks)/len(chunk_results)*100):.1f}%",
                "chunk_summaries": chunk_summaries  # Lighter weight than full chunks
            }
        }
        
        # Merge successful chunk data
        merged_content = {}
        page_ranges = []
        
        for chunk in chunk_results:
            if chunk.get("status") == "success" and chunk.get("data"):
                page_ranges.append(f"Pages {chunk['start_page']}-{chunk['end_page']}")
                
                # Merge chunk data intelligently
                chunk_data = chunk["data"]
                for key, value in chunk_data.items():
                    if key in merged_content:
                        # If key exists, combine values
                        if isinstance(merged_content[key], list) and isinstance(value, list):
                            merged_content[key].extend(value)
                        elif isinstance(merged_content[key], dict) and isinstance(value, dict):
                            merged_content[key].update(value)
                        else:
                            # Convert to list if different types
                            if not isinstance(merged_content[key], list):
                                merged_content[key] = [merged_content[key]]
                            merged_content[key].append(value)
                    else:
                        merged_content[key] = value
        
        combined_data["extracted_data"] = merged_content
        combined_data["page_ranges"] = page_ranges
        combined_data["status"] = "completed" if merged_content else "needs_review"
        
        return combined_data
        
    except Exception as e:
        logger.error(f"Error combining chunk results: {str(e)}")
        return {
            "error": f"Failed to combine chunks: {str(e)}",
            "status": "failed",
            "chunks": chunk_results
        }

# AI Document Processing
async def process_document_with_ai(document_id: str, project: dict):
    """Process document with AI using chunking for large documents"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
        from dotenv import load_dotenv
        import os
        from pathlib import Path
        load_dotenv()
        
        # Get document details
        document = await db.documents.find_one({"id": document_id})
        if not document:
            return
        
        # Get PDF page count
        total_pages = get_pdf_page_count(document["file_path"])
        if total_pages == 0:
            await db.documents.update_one(
                {"id": document_id},
                {"$set": {"status": "failed", "error": "Could not read PDF file"}}
            )
            return
        
        # Determine optimal chunk size based on document size
        def get_optimal_chunk_size(total_pages):
            """Determine optimal chunk size for efficient processing"""
            if total_pages <= 50:
                return 25      # Small docs: 25 pages per chunk
            elif total_pages <= 200:
                return 50      # Medium docs: 50 pages per chunk  
            elif total_pages <= 1000:
                return 100     # Large docs: 100 pages per chunk
            elif total_pages <= 3000:
                return 150     # Very large docs: 150 pages per chunk
            else:
                return 200     # Massive docs: 200 pages per chunk (max efficiency)
        
        PAGES_PER_CHUNK = get_optimal_chunk_size(total_pages)
        chunk_count = (total_pages + PAGES_PER_CHUNK - 1) // PAGES_PER_CHUNK
        use_chunking = chunk_count > 1
        
        logger.info(f"Document optimization: {total_pages} pages → {chunk_count} chunks of {PAGES_PER_CHUNK} pages each")
        
        # Update document with chunk info
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "processing",
                    "total_pages": total_pages,
                    "chunk_count": chunk_count,
                    "chunks_processed": 0,
                    "processing_progress": 5,
                    "processing_message": f"📄 Iniciando procesamiento de {total_pages} páginas...",
                    "chunk_results": []
                }
            }
        )
        
        # Get AI configuration for QA processing
        company = await db.companies.find_one({"id": project["company_id"]})
        if not company:
            logger.error(f"Company not found for project {project['id']}")
            return
        
        ai_config = await get_ai_config_for_task(project["id"], "qa_processing")
        if not ai_config.get("api_key"):
            await db.documents.update_one(
                {"id": document_id},
                {"$set": {"status": "failed", "error": "No AI configuration available"}}
            )
            return
        
        # Create processing prompt
        semantic_instructions = project.get("semantic_instructions", "")
        if not semantic_instructions:
            semantic_instructions = "Extract all key information, dates, names, amounts, and important details from this document."
        
        chunk_results = []
        
        if use_chunking:
            logger.info(f"Processing large PDF ({total_pages} pages) in {chunk_count} chunks of {PAGES_PER_CHUNK} pages each")
            start_time = datetime.now(timezone.utc)
            
            # Process each chunk
            for chunk_idx in range(chunk_count):
                start_page = chunk_idx * PAGES_PER_CHUNK
                end_page = min(start_page + PAGES_PER_CHUNK - 1, total_pages - 1)
                
                # Update progress
                progress = int((chunk_idx / chunk_count) * 80) + 10  # 10-90%
                await db.documents.update_one(
                    {"id": document_id},
                    {
                        "$set": {
                            "processing_progress": progress,
                            "processing_message": f"🤖 Extrayendo datos del chunk {chunk_idx + 1}/{chunk_count} (páginas {start_page + 1}-{end_page + 1})...",
                            "chunks_processed": chunk_idx
                        }
                    }
                )
                
                # Create chunk file
                chunk_filename = f"{document_id}_chunk_{chunk_idx + 1}.pdf"
                chunk_path = Path(document["file_path"]).parent / chunk_filename
                
                if create_pdf_chunk(document["file_path"], start_page, end_page, str(chunk_path)):
                    # Get AI config for data extraction
                    extraction_config = await get_ai_config_for_task(project["id"], "data_extraction")
                    
                    # Calculate chunk-relative page numbers (chunk PDFs start at page 1)
                    chunk_pages = end_page - start_page + 1
                    
                    # Process this chunk with AI
                    # Note: We pass the original page numbers for display purposes,
                    # but the chunk file itself contains pages 1 to chunk_pages
                    chunk_result = await process_single_chunk(
                        str(chunk_path), 
                        semantic_instructions, 
                        extraction_config,
                        chunk_idx + 1,
                        1,  # Chunk PDF always starts at page 1
                        chunk_pages,  # Last page of chunk PDF
                        project["id"],
                        original_start=start_page + 1,  # Pass original page numbers for display
                        original_end=end_page + 1
                    )
                    
                    if chunk_result:
                        chunk_results.append(chunk_result)
                    
                    # Clean up chunk file
                    try:
                        os.remove(str(chunk_path))
                    except:
                        pass
                else:
                    logger.error(f"Failed to create chunk {chunk_idx + 1}")
                
                # Update progress
                chunks_processed = chunk_idx + 1
                progress = int((chunks_processed / chunk_count) * 100)
                await db.documents.update_one(
                    {"id": document_id},
                    {
                        "$set": {
                            "chunks_processed": chunks_processed,
                            "processing_progress": progress,
                            "chunk_results": chunk_results
                        }
                    }
                )
            
            # Combine all chunk results
            combined_data = combine_chunk_results(chunk_results)
            
            # Log performance metrics
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            pages_per_second = total_pages / processing_time if processing_time > 0 else 0
            
            logger.info(f"Chunk processing completed: {total_pages} pages in {processing_time:.1f}s ({pages_per_second:.2f} pages/sec)")
            logger.info(f"Processing efficiency: {chunk_count} chunks processed")
            
        else:
            # Process small document normally
            logger.info(f"Processing small PDF ({total_pages} pages) normally")
            await db.documents.update_one(
                {"id": document_id},
                {"$set": {
                    "processing_progress": 30,
                    "processing_message": f"🤖 Extrayendo datos de {total_pages} páginas..."
                }}
            )
            extraction_config = await get_ai_config_for_task(project["id"], "data_extraction")
            combined_data = await process_single_chunk(
                document["file_path"],
                semantic_instructions,
                extraction_config,
                1,
                1,
                total_pages,
                project["id"]
            )
        
        # Process and store extracted data in normalized format
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {
                "processing_progress": 90,
                "processing_message": "💾 Guardando datos extraídos..."
            }}
        )
        
        if combined_data:
            await store_extracted_data_normalized(document_id, document, project, combined_data)
        
        # Update final document status
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "completed" if combined_data else "failed",
                    "extracted_data": combined_data or {"error": "No data extracted"},
                    "processed_at": datetime.now(timezone.utc),
                    "processing_progress": 100,
                    "processing_message": "✅ Procesamiento completado exitosamente" if combined_data else "❌ Error en el procesamiento"
                }
            }
        )
        
        logger.info(f"Document {document_id} processing completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "failed",
                    "processing_progress": 0,
                    "error": str(e)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        # Update document status to failed
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"status": "failed"}}
        )

# Dashboard stats endpoint
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(
    start_date: str = None,
    end_date: str = None,
    current_user: User = Depends(get_current_user)
):
    # Build date filter
    date_filter = {}
    if start_date or end_date:
        date_filter["created_at"] = {}
        if start_date:
            date_filter["created_at"]["$gte"] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            # Add one day to include the end date
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            date_filter["created_at"]["$lte"] = end_datetime
    
    if current_user.role == "staff":
        # Staff sees all stats
        companies_count = await db.companies.count_documents({})
        projects_count = await db.projects.count_documents({})
        documents_total = await db.documents.count_documents(date_filter)
        documents_completed = await db.documents.count_documents({**date_filter, "status": "completed"})
        documents_failed = await db.documents.count_documents({**date_filter, "status": "failed"})
        documents_processing = await db.documents.count_documents({**date_filter, "status": "processing"})
        documents_needs_review = await db.documents.count_documents({**date_filter, "status": "needs_review"})
        
        # QA statistics
        documents_qa_passed = await db.documents.count_documents({**date_filter, "qa_status": {"$in": ["passed", "approved_manual"]}})
        documents_qa_failed = await db.documents.count_documents({**date_filter, "qa_status": {"$in": ["failed", "rejected_manual"]}})
        documents_qa_pending = await db.documents.count_documents({**date_filter, "qa_status": {"$in": ["pending", "manual_review"]}})
        
        return {
            "companies_count": companies_count,
            "projects_count": projects_count,
            "documents_total": documents_total,
            "documents_completed": documents_completed,
            "documents_failed": documents_failed,
            "documents_processing": documents_processing,
            "documents_needs_review": documents_needs_review,
            "qa_passed": documents_qa_passed,
            "qa_failed": documents_qa_failed,
            "qa_pending": documents_qa_pending
        }
    else:
        # Clients see only their company's stats
        if not current_user.company_id:
            return {"error": "No company assigned"}
        
        project_ids = [p["id"] for p in await db.projects.find({"company_id": current_user.company_id}).to_list(1000)]
        
        projects_count = await db.projects.count_documents({"company_id": current_user.company_id})
        documents_total = await db.documents.count_documents({
            **date_filter,
            "project_id": {"$in": project_ids}
        })
        documents_completed = await db.documents.count_documents({
            **date_filter,
            "project_id": {"$in": project_ids},
            "status": "completed"
        })
        
        return {
            "projects_count": projects_count,
            "documents_total": documents_total,
            "documents_completed": documents_completed
        }

# Document management endpoints
class DocumentRename(BaseModel):
    new_name: str

@api_router.put("/documents/{document_id}/rename", response_model=Document)
async def rename_document(
    document_id: str,
    rename_data: DocumentRename,
    current_user: User = Depends(get_current_user)
):
    # Get document and verify access
    document = await db.documents.find_one({"id": document_id})
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get project to check permissions
    project = await db.projects.find_one({"id": document["project_id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access permissions for clients
    if current_user.role == "client":
        # Get company of this project
        project_company_id = project["company_id"]
        
        # Check if user has access
        has_access = (
            project_company_id in current_user.company_ids or
            project_company_id == current_user.company_id
        )
        
        # Check corporation access if not directly assigned
        if not has_access and current_user.assigned_corporation:
            company = await db.companies.find_one({"id": project_company_id})
            if company and company.get("corporacion") == current_user.assigned_corporation:
                has_access = True
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Update document name
    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"original_filename": rename_data.new_name}}
    )
    
    # Return updated document
    updated_document = await db.documents.find_one({"id": document_id})
    return Document(**updated_document)

@api_router.post("/projects/{project_id}/documents/reorder")
async def reorder_documents_with_ai(
    project_id: str,
    semantic_instructions: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get all completed documents for this project
    documents = await db.documents.find({
        "project_id": project_id,
        "status": "completed"
    }).to_list(1000)
    
    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="No completed documents found for reordering")
    
    # Start AI reordering process in background
    import asyncio
    task_id = str(uuid.uuid4())
    asyncio.create_task(process_document_reordering(project_id, documents, semantic_instructions, task_id))
    
    return {
        "message": "Document reordering started",
        "task_id": task_id,
        "documents_count": len(documents),
        "status": "processing"
    }

@api_router.get("/projects/{project_id}/reorder-status/{task_id}")
async def get_reorder_status(
    project_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    # Check if reordering task status exists
    task_status = await db.reorder_tasks.find_one({"task_id": task_id, "project_id": project_id})
    if not task_status:
        return {"status": "not_found"}
    
    return {
        "status": task_status.get("status", "processing"),
        "progress": task_status.get("progress", 0),
        "result": task_status.get("result", {}),
        "error": task_status.get("error", None)
    }

# AI Document Reordering Function
async def process_document_reordering(project_id: str, documents: list, semantic_instructions: str, task_id: str):
    """Process document reordering with AI based on semantic instructions"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        # Create initial task status
        await db.reorder_tasks.insert_one({
            "task_id": task_id,
            "project_id": project_id,
            "status": "processing",
            "progress": 0
        })
        
        # Get API key
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            await db.reorder_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "failed", "error": "No API key available"}}
            )
            return
        
        # Initialize AI chat
        chat = LlmChat(
            api_key=api_key,
            session_id=f"reorder_{task_id}",
            system_message="You are an expert document organization AI. You analyze document content and metadata to determine optimal ordering and naming based on specific instructions."
        ).with_model("openai", "gpt-4o")
        
        # Prepare document information for AI
        doc_info = []
        for i, doc in enumerate(documents):
            doc_summary = {
                "id": doc["id"],
                "current_name": doc.get("original_filename", f"Document_{i+1}"),
                "extracted_data": doc.get("extracted_data", {}),
                "upload_date": doc.get("created_at", ""),
                "processed_date": doc.get("processed_at", "")
            }
            doc_info.append(doc_summary)
        
        # Update progress
        await db.reorder_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 25}}
        )
        
        # Create AI prompt for reordering
        prompt = f"""
        Analyze the following {len(documents)} documents and provide a reordering and renaming strategy based on these instructions:
        
        INSTRUCTIONS: {semantic_instructions}
        
        DOCUMENTS TO ANALYZE:
        {json.dumps(doc_info, indent=2, default=str)}
        
        Please provide a JSON response with the following structure:
        {{
            "reordering_strategy": "Brief explanation of the ordering logic used",
            "documents": [
                {{
                    "id": "document_id",
                    "new_order": 1,
                    "suggested_name": "New document name",
                    "reasoning": "Why this order and name"
                }}
            ]
        }}
        
        Consider factors like:
        - Document content and type
        - Dates and chronological order
        - Importance and priority
        - Logical workflow or process flow
        - Any patterns in the extracted data
        
        Ensure all document IDs are preserved and each document gets a unique order number starting from 1.
        """
        
        # Update progress
        await db.reorder_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 50}}
        )
        
        # Send to AI
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse AI response
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            raise Exception("Invalid AI response format")
        
        ai_result = json.loads(json_match.group())
        
        # Update progress
        await db.reorder_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 75}}
        )
        
        # Apply the reordering and renaming
        reorder_results = []
        for doc_instruction in ai_result.get("documents", []):
            doc_id = doc_instruction["id"]
            new_order = doc_instruction["new_order"]
            suggested_name = doc_instruction["suggested_name"]
            reasoning = doc_instruction.get("reasoning", "")
            
            # Update document with new order and name
            await db.documents.update_one(
                {"id": doc_id},
                {
                    "$set": {
                        "display_order": new_order,
                        "original_filename": suggested_name,
                        "reorder_reasoning": reasoning,
                        "reordered_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            reorder_results.append({
                "id": doc_id,
                "new_order": new_order,
                "new_name": suggested_name,
                "reasoning": reasoning
            })
        
        # Complete the task
        await db.reorder_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "completed",
                    "progress": 100,
                    "result": {
                        "strategy": ai_result.get("reordering_strategy", ""),
                        "documents": reorder_results,
                        "total_processed": len(reorder_results)
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error in document reordering {task_id}: {str(e)}")
        await db.reorder_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e)
                }
            }
        )

# Additional Models for new features
class QAAgent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    qa_instructions: str
    project_ids: List[str] = []  # Empty list means universal
    is_universal: bool = False
    is_active: bool = True
    auto_process: bool = True  # If true, runs automatically on upload
    quality_checks: Dict[str, bool] = {
        "image_clarity": False,
        "document_orientation": False,
        "signature_detection": False,
        "seal_detection": False,
        "text_readability": False,
        "completeness_check": False
    }
    # QA thresholds
    critical_threshold: int = 80  # Score below this requires manual review
    pass_threshold: int = 60      # Score below this fails QA
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # user id

class QAAgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    qa_instructions: str
    project_ids: List[str] = []
    is_universal: bool = False
    auto_process: bool = True
    quality_checks: Dict[str, bool]
    critical_threshold: Optional[int] = 80
    pass_threshold: Optional[int] = 60

class DocumentProcessRequest(BaseModel):
    semantic_instructions: str

class AIQuestionRequest(BaseModel):
    question: str
    include_context: bool = True

# QA Findings and Management endpoints
@api_router.get("/projects/{project_id}/qa-findings")
async def get_qa_findings(project_id: str, current_user: User = Depends(get_current_user)):
    """Get documents with QA findings for manual review"""
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get documents with QA issues (manual_review or failed status)
    # Include ALL documents that need review, not just those with critical findings
    documents = await db.documents.find({
        "project_id": project_id,
        "qa_status": {"$in": ["failed", "manual_review"]},
        "qa_results": {"$exists": True}
    }).to_list(1000)
    
    qa_findings_summary = []
    
    for doc in documents:
        # Get ALL findings from agent results, not just critical ones
        all_findings = []
        agent_results = doc.get("qa_results", {}).get("agent_results", [])
        for agent_result in agent_results:
            agent_name = agent_result.get("agent_name", "Unknown Agent")
            findings = agent_result.get("findings", [])
            for finding in findings:
                all_findings.append({
                    "agent": agent_name,
                    "finding": finding,
                    "document_id": doc["id"]
                })
        
        qa_score = doc.get("qa_results", {}).get("overall_score", 0)
        
        qa_findings_summary.append({
            "document_id": doc["id"],
            "filename": doc["original_filename"],
            "qa_status": doc["qa_status"],
            "qa_score": qa_score,
            "findings_count": len(all_findings),
            "critical_findings": all_findings,  # Now includes all findings, not just critical
            "qa_processed_at": doc.get("qa_processed_at"),
            "status": doc["status"]
        })
    
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "documents_with_findings": qa_findings_summary,
        "summary": {
            "total_documents_with_issues": len(qa_findings_summary),
            "failed_qa": len([d for d in qa_findings_summary if d["qa_status"] == "failed"]),
            "manual_review": len([d for d in qa_findings_summary if d["qa_status"] == "manual_review"])
        }
    }

@api_router.post("/documents/{document_id}/qa-approve")
async def approve_document_after_review(
    document_id: str,
    approval_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Approve document after manual QA review"""
    if current_user.role not in ["staff", "asesor"]:
        raise HTTPException(status_code=403, detail="Only staff can approve documents")
    
    document = await db.documents.find_one({"id": document_id})
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.get("qa_status") not in ["manual_review", "failed"]:
        raise HTTPException(status_code=400, detail="Document is not pending manual review")
    
    action = approval_data.get("action")  # "approve", "reject", "request_reupload"
    comments = approval_data.get("comments", "")
    
    if action == "approve":
        # Get project for AI processing
        project = await db.projects.find_one({"id": document["project_id"]})
        
        # Update document and start AI processing
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "processing",
                    "qa_status": "approved_manual",
                    "qa_approved_by": current_user.id,
                    "qa_approved_at": datetime.now(timezone.utc),
                    "qa_approval_comments": comments
                }
            }
        )
        
        # Start AI processing
        asyncio.create_task(process_document_with_ai(document_id, project))
        
        return {"message": "Document approved and processing started", "status": "processing"}
        
    elif action == "reject":
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "qa_failed",
                    "qa_status": "rejected_manual",
                    "qa_approved_by": current_user.id,
                    "qa_approved_at": datetime.now(timezone.utc),
                    "qa_approval_comments": comments
                }
            }
        )
        return {"message": "Document rejected", "status": "qa_failed"}
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

@api_router.get("/projects/{project_id}/qa-summary")
async def get_project_qa_summary(project_id: str, current_user: User = Depends(get_current_user)):
    """Get QA summary stats for a project"""
    # Verify access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get QA statistics
    total_docs = await db.documents.count_documents({"project_id": project_id})
    qa_passed = await db.documents.count_documents({
        "project_id": project_id,
        "qa_status": {"$in": ["passed", "approved_manual"]}
    })
    qa_failed = await db.documents.count_documents({
        "project_id": project_id,
        "qa_status": {"$in": ["failed", "rejected_manual"]}
    })
    manual_review = await db.documents.count_documents({
        "project_id": project_id,
        "qa_status": "manual_review"
    })
    qa_pending = await db.documents.count_documents({
        "project_id": project_id,
        "qa_status": {"$in": ["pending", None]}
    })
    
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "qa_summary": {
            "total_documents": total_docs,
            "qa_passed": qa_passed,
            "qa_failed": qa_failed,
            "manual_review_needed": manual_review,
            "qa_pending": qa_pending,
            "pass_rate": f"{(qa_passed/total_docs*100):.1f}%" if total_docs > 0 else "0%"
        }
    }

# QA Agents endpoints
@api_router.post("/qa-agents", response_model=QAAgent)
async def create_qa_agent(agent_data: QAAgentCreate, current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can create QA agents")
    
    agent_dict = agent_data.dict()
    agent_dict["created_by"] = current_user.id
    agent = QAAgent(**agent_dict)
    
    await db.qa_agents.insert_one(agent.dict())
    return agent

@api_router.put("/qa-agents/{agent_id}", response_model=QAAgent)
async def update_qa_agent(agent_id: str, agent_data: QAAgentCreate, current_user: User = Depends(get_current_user)):
    if current_user.role not in ["staff"]:
        raise HTTPException(status_code=403, detail="Only staff can update QA agents")
    
    # Check if agent exists
    existing_agent = await db.qa_agents.find_one({"id": agent_id})
    if not existing_agent:
        raise HTTPException(status_code=404, detail="QA Agent not found")
    
    # Update agent
    update_data = agent_data.dict()
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db.qa_agents.update_one(
        {"id": agent_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="QA Agent not found")
    
    # Return updated agent
    updated_agent = await db.qa_agents.find_one({"id": agent_id})
    return QAAgent(**updated_agent)

@api_router.delete("/qa-agents/{agent_id}")
async def delete_qa_agent(agent_id: str, current_user: User = Depends(get_current_user)):
    if current_user.role not in ["staff"]:
        raise HTTPException(status_code=403, detail="Only staff can delete QA agents")
    
    # Check if agent exists
    agent = await db.qa_agents.find_one({"id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="QA Agent not found")
    
    # Check if agent is being used by any documents currently in QA
    documents_in_qa = await db.documents.count_documents({
        "qa_status": {"$in": ["pending", "manual_review"]},
        "$or": [
            {"project_id": {"$in": agent.get("project_ids", [])}},
            {"qa_results.agent_results.agent_id": agent_id}
        ]
    })
    
    if documents_in_qa > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete QA agent. {documents_in_qa} documents are currently using this agent in QA process."
        )
    
    # Delete the agent
    result = await db.qa_agents.delete_one({"id": agent_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="QA Agent not found")
    
    return {"message": "QA Agent deleted successfully", "agent_id": agent_id}

@api_router.get("/qa-agents", response_model=List[QAAgent])
async def get_qa_agents(current_user: User = Depends(get_current_user)):
    agents = await db.qa_agents.find().to_list(1000)
    return [QAAgent(**agent) for agent in agents]

@api_router.post("/qa-agents/{agent_id}/run")
async def run_qa_agent(agent_id: str, current_user: User = Depends(get_current_user)):
    agent = await db.qa_agents.find_one({"id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="QA Agent not found")
    
    # Start QA process in background
    import asyncio
    task_id = str(uuid.uuid4())
    asyncio.create_task(process_qa_check(agent_id, task_id))
    
    return {"message": "QA check started", "task_id": task_id}

# User management endpoints
@api_router.get("/users", response_model=List[User])
async def get_users(current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can view users")
    
    users = await db.users.find().to_list(1000)
    # Ensure backward compatibility with users missing new fields
    result = []
    for user in users:
        # Set defaults for new fields if they don't exist
        if 'company_ids' not in user:
            user['company_ids'] = []
        if 'assigned_corporation' not in user:
            user['assigned_corporation'] = None
        result.append(User(**user))
    return result

@api_router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(user_id: str, status_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can modify users")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": status_data["is_active"]}}
    )
    
    return {"message": "User status updated"}


@api_router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    password_data: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Reset password for a user. Only staff can reset passwords.
    """
    # Only staff can reset passwords
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Solo el staff puede reiniciar contraseñas")
    
    # Check if user exists
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Prevent resetting own password through this endpoint
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes reiniciar tu propia contraseña a través de este método. Usa 'Cambiar Contraseña'")
    
    # Get new password from request
    new_password = password_data.get("new_password")
    if not new_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña es requerida")
    
    # Validate password length
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    
    # Hash the new password
    hashed_password = get_password_hash(new_password)
    
    # Update user password
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hashed_password}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Error al actualizar la contraseña")
    
    return {
        "message": "Contraseña reiniciada exitosamente",
        "user_id": user_id,
        "user_email": user.get("email")
    }


@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: User = Depends(get_current_user)):
    # Only staff can delete users
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can delete users")
    
    # Check if user exists
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Protect admin account
    if user.get("email") == "admin@pergaminos.com":
        raise HTTPException(
            status_code=403, 
            detail="No se puede eliminar el usuario administrador principal"
        )
    
    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user account")
    
    # Check if user is assigned as asesor comercial to any companies
    companies_assigned = await db.companies.count_documents({"asesor_comercial_id": user_id})
    if companies_assigned > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete user. User is assigned as asesor comercial to {companies_assigned} companies. Reassign companies first."
        )
    
    # Delete the user
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully", "user_id": user_id}

# Document processing endpoints - Enhanced version
@api_router.post("/projects/{project_id}/documents/process-rename-reorder")
async def process_documents_rename_reorder(
    project_id: str,
    document_changes: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        changes = json.loads(document_changes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid document changes format")
    
    # Get documents that have changes
    document_ids = list(changes.keys())
    documents = await db.documents.find({
        "id": {"$in": document_ids},
        "project_id": project_id,
        "status": "completed"
    }).to_list(1000)
    
    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="No valid documents found for processing")
    
    # Start processing in background
    import asyncio
    task_id = str(uuid.uuid4())
    asyncio.create_task(process_document_changes(project_id, documents, changes, task_id))
    
    return {
        "message": "Document processing started",
        "task_id": task_id,
        "documents_count": len(documents),
        "status": "processing"
    }

@api_router.get("/projects/{project_id}/download-processed/{task_id}")
async def download_processed_documents(
    project_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get task status
    task_status = await db.process_tasks.find_one({"task_id": task_id, "project_id": project_id})
    if not task_status or task_status.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Processed file not found or not ready")
    
    # Generate a simple PDF with the processed document information
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io
        
        # Create PDF in memory
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, 750, f"Documentos Procesados - {project['name']}")
        
        # Date
        p.setFont("Helvetica", 10)
        p.drawString(50, 730, f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Document list
        y_position = 700
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y_position, "Lista de Documentos Procesados:")
        y_position -= 30
        
        # Get processed documents
        documents = await db.documents.find({
            "project_id": project_id,
            "status": "completed"
        }).sort("display_order", 1).to_list(1000)
        
        p.setFont("Helvetica", 10)
        for i, doc in enumerate(documents):
            if y_position < 50:  # Start new page if needed
                p.showPage()
                y_position = 750
            
            order = doc.get("display_order", i + 1)
            name = doc.get("original_filename", "Documento sin nombre")
            p.drawString(50, y_position, f"{order}. {name}")
            
            if doc.get("reorder_reasoning"):
                y_position -= 15
                p.setFont("Helvetica-Oblique", 8)
                p.drawString(70, y_position, f"IA: {doc.get('reorder_reasoning')[:100]}...")
                p.setFont("Helvetica", 10)
            
            y_position -= 20
        
        p.save()
        buffer.seek(0)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            io.BytesIO(buffer.read()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=documentos_procesados_{project_id}.pdf"}
        )
        
    except ImportError:
        # Fallback if reportlab is not available
        # Return a simple text response
        from fastapi.responses import PlainTextResponse
        
        documents = await db.documents.find({
            "project_id": project_id,
            "status": "completed"
        }).sort("display_order", 1).to_list(1000)
        
        content = f"Documentos Procesados - {project['name']}\n"
        content += f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for i, doc in enumerate(documents):
            order = doc.get("display_order", i + 1)
            name = doc.get("original_filename", "Documento sin nombre")
            content += f"{order}. {name}\n"
            if doc.get("reorder_reasoning"):
                content += f"   IA: {doc.get('reorder_reasoning')}\n"
        
        return PlainTextResponse(
            content,
            headers={"Content-Disposition": f"attachment; filename=documentos_procesados_{project_id}.txt"}
        )

# Enhanced background processing function
async def process_document_changes(project_id: str, documents: list, changes: dict, task_id: str):
    """Process individual document changes"""
    try:
        # Create task status
        await db.process_tasks.insert_one({
            "task_id": task_id,
            "project_id": project_id,
            "status": "processing",
            "progress": 0
        })
        
        # Update progress
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 25}}
        )
        
        # Apply changes to each document
        processed_count = 0
        total_docs = len(documents)
        
        for document in documents:
            doc_id = document["id"]
            if doc_id in changes:
                change = changes[doc_id]
                new_name = change.get("newName", document["original_filename"])
                new_order = change.get("newOrder", 1)
                
                # Update document in database
                await db.documents.update_one(
                    {"id": doc_id},
                    {
                        "$set": {
                            "original_filename": new_name,
                            "display_order": new_order,
                            "reorder_reasoning": f"Renombrado a '{new_name}' y reordenado a posición {new_order}",
                            "reordered_at": datetime.now(timezone.utc)
                        }
                    }
                )
                
                processed_count += 1
                
                # Update progress
                progress = 25 + int((processed_count / total_docs) * 50)
                await db.process_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"progress": progress}}
                )
        
        # Update progress to 75%
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 75}}
        )
        
        # Generate download URL
        download_url = f"/api/projects/{project_id}/download-processed/{task_id}"
        
        # Complete task
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "completed",
                    "progress": 100,
                    "download_url": download_url,
                    "result": {
                        "processed_documents": processed_count,
                        "total_documents": total_docs
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error in document changes processing {task_id}: {str(e)}")
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )

# Document processing endpoints (keep original for backward compatibility)
@api_router.post("/projects/{project_id}/documents/process-reorder")
async def process_documents_reorder(
    project_id: str,
    semantic_instructions: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get completed documents
    documents = await db.documents.find({
        "project_id": project_id,
        "status": "completed"
    }).to_list(1000)
    
    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="No completed documents found")
    
    # Start processing in background
    import asyncio
    task_id = str(uuid.uuid4())
    asyncio.create_task(process_document_reordering_with_pdf(project_id, documents, semantic_instructions, task_id))
    
    return {
        "message": "Document processing started",
        "task_id": task_id,
        "documents_count": len(documents),
        "status": "processing"
    }

@api_router.get("/projects/{project_id}/process-status/{task_id}")
async def get_process_status(
    project_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    task_status = await db.process_tasks.find_one({"task_id": task_id, "project_id": project_id})
    if not task_status:
        return {"status": "not_found"}
    
    return {
        "status": task_status.get("status", "processing"),
        "progress": task_status.get("progress", 0),
        "download_url": task_status.get("download_url", None),
        "error": task_status.get("error", None)
    }

# AI question endpoint for clients
@api_router.post("/projects/{project_id}/ask-ai")
async def ask_ai_about_documents(
    project_id: str,
    question_data: AIQuestionRequest,
    current_user: User = Depends(get_current_user)
):
    # Verify project access
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get documents with extracted data
    documents = await db.documents.find({
        "project_id": project_id,
        "status": "completed",
        "extracted_data": {"$exists": True, "$ne": None}
    }).to_list(1000)
    
    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="No processed documents found")
    
    # Process with AI
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not available")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"client_query_{current_user.id}_{project_id}",
            system_message="You are a helpful AI assistant that answers questions about document data. Provide clear, accurate answers based on the extracted document data provided. Always cite which documents you used to answer."
        ).with_model("openai", "gpt-4o")
        
        # Prepare context from extracted data with document IDs
        context = "Available documents:\n\n"
        doc_map = {}  # Map filename to document data
        
        for idx, doc in enumerate(documents):
            if doc.get("extracted_data"):
                doc_id = f"DOC_{idx}"
                context += f"[{doc_id}] Filename: {doc['original_filename']}\n"
                context += f"Data: {json.dumps(doc['extracted_data'], indent=2)}\n\n"
                doc_map[doc_id] = {
                    "document_id": doc['id'],
                    "filename": doc['original_filename'],
                    "file_path": doc.get('file_path', '')
                }
        
        prompt = f"""
        Based on the document data above, answer this question: {question_data.question}
        
        {context}
        
        IMPORTANT: At the end of your answer, list ONLY the document IDs (e.g., [DOC_0], [DOC_1]) that you actually used to answer this question.
        Format your response like this:
        
        [Your answer here]
        
        USED_DOCS: [DOC_X, DOC_Y, ...]
        
        If no documents contain relevant information, say so clearly and use USED_DOCS: []
        Responde en español, pero mantén el formato USED_DOCS en inglés.
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse response to extract used documents
        used_sources = []
        answer = response
        
        if "USED_DOCS:" in response:
            parts = response.split("USED_DOCS:")
            answer = parts[0].strip()
            
            # Extract document IDs from the USED_DOCS line
            used_docs_str = parts[1].strip()
            import re
            doc_ids = re.findall(r'DOC_\d+', used_docs_str)
            
            # Map back to actual documents
            for doc_id in doc_ids:
                if doc_id in doc_map:
                    used_sources.append(doc_map[doc_id])
        else:
            # Fallback: if AI didn't follow format, limit to first 3 docs
            used_sources = list(doc_map.values())[:3]
        
        return {
            "answer": answer,
            "sources": used_sources,
            "documents_consulted": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error processing AI question: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing question")


@api_router.get("/client/download-document/{document_id}")
async def client_download_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Allow client to download a document PDF.
    Only allows download if document belongs to client's company.
    """
    try:
        # Get document
        document = await db.documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get project to verify company
        project = await db.projects.find_one({"id": document["project_id"]})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Verify client has access (must be from same company)
        if current_user.role == "client":
            if current_user.company_id != project["company_id"]:
                raise HTTPException(status_code=403, detail="Access denied to this document")
        elif current_user.role == "asesor":
            # Asesor can access if they manage the company
            company = await db.companies.find_one({"id": project["company_id"]})
            if company.get("asesor_comercial_id") != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied to this document")
        # Staff can access all
        
        # Get file path
        file_path = Path(document["file_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Document file not found on server")
        
        # Stream file
        def iterfile():
            with open(file_path, mode="rb") as file:
                yield from file
        
        return StreamingResponse(
            iterfile(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={document['original_filename']}",
                "Content-Type": "application/pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document for client: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Background processing functions
async def process_qa_check(agent_id: str, task_id: str):
    """Process QA check with AI"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        # Get agent details
        agent = await db.qa_agents.find_one({"id": agent_id})
        if not agent:
            return
            
        # Create task status
        await db.qa_tasks.insert_one({
            "task_id": task_id,
            "agent_id": agent_id,
            "status": "processing",
            "progress": 0
        })
        
        # Get documents to check
        if agent["is_universal"]:
            documents = await db.documents.find({"status": "completed"}).to_list(1000)
        else:
            documents = await db.documents.find({
                "project_id": {"$in": agent["project_ids"]},
                "status": "completed"
            }).to_list(1000)
        
        # Process QA checks with AI (simplified version)
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if api_key:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"qa_check_{task_id}",
                system_message="You are a document quality assessment AI. Analyze documents for quality issues."
            ).with_model("openai", "gpt-4o")
            
            # Simulate QA processing
            await db.qa_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"progress": 50}}
            )
            
            # Complete QA check
            await db.qa_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "completed", "progress": 100}}
            )
        
    except Exception as e:
        logger.error(f"Error in QA check {task_id}: {str(e)}")
        await db.qa_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )

async def process_document_reordering_with_pdf(project_id: str, documents: list, semantic_instructions: str, task_id: str):
    """Process documents and generate PDF"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        # Create task status
        await db.process_tasks.insert_one({
            "task_id": task_id,
            "project_id": project_id,
            "status": "processing",
            "progress": 0
        })
        
        # Process with AI (similar to existing reorder function)
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            await db.process_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "failed", "error": "No API key available"}}
            )
            return
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"process_{task_id}",
            system_message="You are a document processing AI. Analyze and organize documents based on instructions."
        ).with_model("openai", "gpt-4o")
        
        # Update progress
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 25}}
        )
        
        # Prepare document info for AI
        doc_info = []
        for i, doc in enumerate(documents):
            doc_summary = {
                "id": doc["id"],
                "name": doc.get("original_filename", f"Document_{i+1}"),
                "extracted_data": doc.get("extracted_data", {}),
                "created_at": doc.get("created_at", "")
            }
            doc_info.append(doc_summary)
        
        # AI processing prompt
        prompt = f"""
        Process these {len(documents)} documents according to these instructions:
        
        INSTRUCTIONS: {semantic_instructions}
        
        DOCUMENTS:
        {json.dumps(doc_info, indent=2, default=str)}
        
        Provide a JSON response with:
        {{
            "processing_strategy": "Brief explanation",
            "documents": [
                {{
                    "id": "document_id",
                    "new_order": 1,
                    "suggested_name": "New name",
                    "reasoning": "Why this order/name"
                }}
            ]
        }}
        """
        
        # Update progress
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 50}}
        )
        
        # Send to AI
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse response
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            raise Exception("Invalid AI response format")
        
        ai_result = json.loads(json_match.group())
        
        # Update progress
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"progress": 75}}
        )
        
        # Generate PDF (simplified - just create a download URL)
        # In a real implementation, you would merge PDFs according to the new order
        download_url = f"/api/projects/{project_id}/download-processed/{task_id}"
        
        # Complete task
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "completed",
                    "progress": 100,
                    "download_url": download_url,
                    "result": ai_result
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error in document processing {task_id}: {str(e)}")
        await db.process_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )

# Segmentos management endpoints
@api_router.post("/segmentos", response_model=Segmento)
async def create_segmento(segmento_data: SegmentoCreate, current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can create segmentos")
    
    segmento_dict = segmento_data.dict()
    segmento_dict["created_by"] = current_user.id
    segmento = Segmento(**segmento_dict)
    
    await db.segmentos.insert_one(segmento.dict())
    return segmento

@api_router.put("/segmentos/{segmento_id}", response_model=Segmento)
async def update_segmento(
    segmento_id: str, 
    segmento_data: SegmentoCreate, 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can update segmentos")
    
    # Check if segmento exists
    existing_segmento = await db.segmentos.find_one({"id": segmento_id})
    if not existing_segmento:
        raise HTTPException(status_code=404, detail="Segmento not found")
    
    # Update segmento
    update_data = segmento_data.dict()
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db.segmentos.update_one(
        {"id": segmento_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Segmento not found")
    
    # Get updated segmento
    updated_segmento = await db.segmentos.find_one({"id": segmento_id})
    return Segmento(**updated_segmento)

@api_router.get("/segmentos", response_model=List[Segmento])
async def get_segmentos():
    # All users can see active segmentos for selection
    segmentos = await db.segmentos.find({"is_active": True}).to_list(1000)
    return [Segmento(**segmento) for segmento in segmentos]

@api_router.delete("/segmentos/{segmento_id}")
async def delete_segmento(segmento_id: str, current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can delete segmentos")
    
    # Check if segmento is being used by any company
    companies_using = await db.companies.count_documents({"segmento": segmento_id})
    if companies_using > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete segmento. {companies_using} companies are using this segmento."
        )
    
    result = await db.segmentos.delete_one({"id": segmento_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Segmento not found")
    
    return {"message": "Segmento deleted successfully", "segmento_id": segmento_id}

# ========== CORPORATION ENDPOINTS ==========

@api_router.post("/corporations", response_model=Corporation)
async def create_corporation(
    corporation_data: CorporationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new corporation (staff only)"""
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can create corporations")
    
    # Check if corporation with same name already exists
    existing = await db.corporations.find_one({"name": corporation_data.name.strip(), "is_active": True})
    if existing:
        raise HTTPException(status_code=400, detail="Corporation with this name already exists")
    
    corporation = Corporation(
        name=corporation_data.name.strip(),
        created_by=current_user.id
    )
    
    await db.corporations.insert_one(corporation.dict())
    logger.info(f"Corporation created: {corporation.name} by {current_user.email}")
    
    return corporation

@api_router.get("/corporations", response_model=List[Corporation])
async def get_corporations(current_user: User = Depends(get_current_user)):
    """Get all active corporations"""
    # All authenticated users can see corporations for selection
    corporations = await db.corporations.find({"is_active": True}).sort("name", 1).to_list(1000)
    return [Corporation(**corp) for corp in corporations]

@api_router.delete("/corporations/{corporation_id}")
async def delete_corporation(
    corporation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a corporation (staff only)"""
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can delete corporations")
    
    # Check if corporation is being used by any company
    companies_using = await db.companies.count_documents({"corporation": corporation_id, "is_active": True})
    if companies_using > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete corporation. {companies_using} companies are using this corporation."
        )
    
    result = await db.corporations.delete_one({"id": corporation_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Corporation not found")
    
    logger.info(f"Corporation deleted: {corporation_id} by {current_user.email}")
    return {"message": "Corporation deleted successfully", "corporation_id": corporation_id}

# Endpoint to get users with specific role (for asesor assignment)
@api_router.get("/users/asesores", response_model=List[User])
async def get_asesores(current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can view asesores")
    
    asesores = await db.users.find({"role": "asesor", "is_active": True}).to_list(1000)
    return [User(**asesor) for asesor in asesores]

# AI Configuration Management Endpoints
@api_router.post("/projects/{project_id}/ai-config", response_model=AIConfiguration)
async def create_ai_configuration(
    project_id: str,
    config_data: AIConfigurationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create AI configuration for a project"""
    if current_user.role not in ["staff"]:
        raise HTTPException(status_code=403, detail="Only staff can manage AI configurations")
    
    # Verify project exists
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if configuration for this type already exists
    existing_config = await db.ai_configurations.find_one({
        "project_id": project_id,
        "config_type": config_data.config_type,
        "is_active": True
    })
    
    if existing_config:
        raise HTTPException(
            status_code=400, 
            detail=f"Active configuration for {config_data.config_type} already exists"
        )
    
    # Encrypt API key if provided
    encrypted_key = None
    if config_data.api_key:
        try:
            encrypted_key = encrypt_api_key(config_data.api_key)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid API key format")
    
    # Create configuration
    ai_config = AIConfiguration(
        project_id=project_id,
        config_type=config_data.config_type,
        provider=config_data.provider,
        api_key=encrypted_key,
        model_name=config_data.model_name,
        model_parameters=config_data.model_parameters,
        created_by=current_user.id
    )
    
    await db.ai_configurations.insert_one(ai_config.dict())
    
    # Return config without API key for security
    response_config = ai_config.dict()
    response_config["api_key"] = "***ENCRYPTED***" if encrypted_key else None
    
    return AIConfiguration(**response_config)

@api_router.get("/projects/{project_id}/ai-config")
async def get_ai_configurations(
    project_id: str,
    config_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get AI configurations for a project"""
    # Verify access to project
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify access to company that owns the project
    company = await db.companies.find_one({"id": project["company_id"]})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Build query
    query = {"project_id": project_id, "is_active": True}
    if config_type:
        query["config_type"] = config_type
    
    # Get configurations
    configs = await db.ai_configurations.find(query).to_list(1000)
    
    # Convert to response format and remove API keys for security
    config_responses = []
    for config in configs:
        config_dict = dict(config)
        config_dict["api_key"] = "***ENCRYPTED***" if config.get("api_key") else None
        # Remove MongoDB ObjectId if present
        if "_id" in config_dict:
            del config_dict["_id"]
        config_responses.append(config_dict)
    
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "company_id": project["company_id"],
        "company_name": company["name"],
        "configurations": config_responses,
        "available_types": ["data_extraction", "qa_processing", "document_processing"]
    }

@api_router.put("/projects/{project_id}/ai-config/{config_id}")
async def update_ai_configuration(
    project_id: str,
    config_id: str,
    update_data: AIConfigurationUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update AI configuration"""
    if current_user.role not in ["staff"]:
        raise HTTPException(status_code=403, detail="Only staff can update AI configurations")
    
    # Find existing configuration
    existing_config = await db.ai_configurations.find_one({
        "id": config_id,
        "project_id": project_id
    })
    
    if not existing_config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Prepare update data
    update_fields = {}
    for field, value in update_data.dict(exclude_unset=True).items():
        if field == "api_key" and value:
            # Encrypt new API key
            try:
                update_fields["api_key"] = encrypt_api_key(value)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid API key format")
        else:
            update_fields[field] = value
    
    update_fields["updated_at"] = datetime.now(timezone.utc)
    
    # Update configuration
    result = await db.ai_configurations.update_one(
        {"id": config_id, "project_id": project_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return {"message": "Configuration updated successfully", "config_id": config_id}

@api_router.delete("/projects/{project_id}/ai-config/{config_id}")
async def delete_ai_configuration(
    project_id: str,
    config_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete/deactivate AI configuration"""
    if current_user.role not in ["staff"]:
        raise HTTPException(status_code=403, detail="Only staff can delete AI configurations")
    
    # Soft delete - just deactivate
    result = await db.ai_configurations.update_one(
        {"id": config_id, "project_id": project_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return {"message": "Configuration deactivated successfully", "config_id": config_id}

# OCR Configuration endpoints (Global)
@api_router.get("/ocr-config", response_model=OCRConfig)
async def get_ocr_config(current_user: User = Depends(get_current_user)):
    """Get global OCR configuration"""
    config = await db.ocr_config.find_one({"id": "global_ocr_config"})
    
    if not config:
        # Create default configuration if it doesn't exist
        default_config = OCRConfig()
        await db.ocr_config.insert_one(default_config.dict())
        return default_config
    
    return OCRConfig(**config)

@api_router.post("/ocr-config")
async def update_ocr_config(
    config_update: OCRConfigUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update global OCR configuration (staff only)"""
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can update OCR configuration")
    
    # Validate ocr_method if provided
    if config_update.ocr_method and config_update.ocr_method not in ["tesseract", "gpt4o_vision"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid OCR method. Must be 'tesseract' or 'gpt4o_vision'"
        )
    
    # Build update data
    update_data = {
        "updated_at": datetime.now(timezone.utc),
        "updated_by": current_user.id
    }
    
    if config_update.ocr_enabled is not None:
        update_data["ocr_enabled"] = config_update.ocr_enabled
    
    if config_update.ocr_method:
        update_data["ocr_method"] = config_update.ocr_method
    
    # Update or create configuration
    result = await db.ocr_config.update_one(
        {"id": "global_ocr_config"},
        {"$set": update_data},
        upsert=True
    )
    
    return {
        "message": "OCR configuration updated successfully",
        "ocr_enabled": config_update.ocr_enabled,
        "ocr_method": config_update.ocr_method
    }

@api_router.get("/ai-models/recommendations")
async def get_model_recommendations():
    """Get recommended models for each AI task type"""
    return {
        "data_extraction": {
            "recommended": [
                {
                    "model": "gpt-4o",
                    "description": "Mejor balance precisión/velocidad para extracción de datos estructurados",
                    "use_case": "Documentos complejos, múltiples campos",
                    "cost_level": "medium"
                },
                {
                    "model": "gpt-4o-mini",
                    "description": "Económico y rápido para extracciones simples",
                    "use_case": "Documentos simples, pocos campos",
                    "cost_level": "low"
                },
                {
                    "model": "gpt-4-turbo",
                    "description": "Máxima precisión para documentos críticos",
                    "use_case": "Documentos legales, financieros",
                    "cost_level": "high"
                }
            ]
        },
        "qa_processing": {
            "recommended": [
                {
                    "model": "gpt-4o-mini",
                    "description": "Optimal para análisis de calidad rápido",
                    "use_case": "Control de calidad automático, detección de problemas",
                    "cost_level": "low"
                },
                {
                    "model": "gpt-4o",
                    "description": "Análisis de calidad detallado",
                    "use_case": "Documentos críticos, análisis profundo",
                    "cost_level": "medium"
                }
            ]
        },
        "document_processing": {
            "recommended": [
                {
                    "model": "gpt-4o",
                    "description": "Procesamiento general de documentos",
                    "use_case": "Reordenamiento, clasificación, resúmenes",
                    "cost_level": "medium"
                },
                {
                    "model": "gpt-4-turbo",
                    "description": "Procesamiento de documentos largos",
                    "use_case": "PDFs de múltiples páginas, análisis complejo",
                    "cost_level": "high"
                }
            ]
        }
    }

# Extracted Data Management Endpoints
@api_router.get("/companies/{company_id}/extracted-data")
async def get_company_extracted_data(
    company_id: str, 
    project_id: Optional[str] = None,
    field_name: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get all extracted data for a company, optionally filtered by project or field"""
    # Verify access to company
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check permissions
    if current_user.role == "client" and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Build query
    query = {"company_id": company_id}
    if project_id:
        query["project_id"] = project_id
    if field_name:
        query["field_name"] = field_name
    
    # Get extracted data
    extracted_data = await db.extracted_data.find(query).sort("extracted_at", -1).to_list(10000)
    
    # Group by document for better organization
    documents_data = {}
    for item in extracted_data:
        doc_id = item["document_id"]
        if doc_id not in documents_data:
            documents_data[doc_id] = {
                "document_id": doc_id,
                "document_name": item["document_name"],
                "project_id": item["project_id"],
                "extracted_at": item["extracted_at"],
                "fields": []
            }
        
        documents_data[doc_id]["fields"].append({
            "field_name": item["field_name"],
            "field_value": item["field_value"],
            "field_type": item.get("field_type"),
            "confidence": item.get("confidence"),
            "page_number": item.get("page_number")
        })
    
    return {
        "company_id": company_id,
        "company_name": company["name"],
        "total_documents": len(documents_data),
        "total_fields": len(extracted_data),
        "documents": list(documents_data.values())
    }

@api_router.get("/companies/{company_id}/data-summary")
async def get_company_data_summary(
    company_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get summary of extracted data types and counts for a company"""
    # Verify access
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if current_user.role == "client" and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Aggregate data by field types
    pipeline = [
        {"$match": {"company_id": company_id}},
        {"$group": {
            "_id": "$field_name",
            "count": {"$sum": 1},
            "unique_values": {"$addToSet": "$field_value"},
            "avg_confidence": {"$avg": "$confidence"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    field_summary = await db.extracted_data.aggregate(pipeline).to_list(1000)
    
    return {
        "company_id": company_id,
        "company_name": company["name"],
        "field_summary": field_summary,
        "total_unique_fields": len(field_summary)
    }

# Delete endpoints (only for admin/staff)
@api_router.delete("/companies/{company_id}")
async def delete_company(company_id: str, current_user: User = Depends(get_current_user)):
    # Only staff can delete companies
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can delete companies")
    
    # Check if company exists
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if there are projects associated with this company
    projects_count = await db.projects.count_documents({"company_id": company_id})
    if projects_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete company. There are {projects_count} projects associated with this company. Delete projects first."
        )
    
    # Check if there are users associated with this company
    users_count = await db.users.count_documents({"company_id": company_id})
    if users_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete company. There are {users_count} users associated with this company. Update users first."
        )
    
    # Delete the company
    result = await db.companies.delete_one({"id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {"message": "Company deleted successfully", "company_id": company_id}


@api_router.put("/projects/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user)
):
    # Get existing project
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access permissions for clients
    if current_user.role == "client":
        # Get company of this project
        project_company_id = project["company_id"]
        
        # Check if user has access
        has_access = (
            project_company_id in current_user.company_ids or
            project_company_id == current_user.company_id
        )
        
        # Check corporation access if not directly assigned
        if not has_access and current_user.assigned_corporation:
            company = await db.companies.find_one({"id": project_company_id})
            if company and company.get("corporacion") == current_user.assigned_corporation:
                has_access = True
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate project_code uniqueness if changed
    if project_data.project_code and project_data.project_code != project.get("project_code"):
        existing_project = await db.projects.find_one({
            "project_code": project_data.project_code,
            "company_id": project["company_id"],
            "id": {"$ne": project_id}
        })
        if existing_project:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un proyecto con el ID '{project_data.project_code}' en esta empresa"
            )
    
    # Update project
    update_data = project_data.dict(exclude_unset=True)
    await db.projects.update_one(
        {"id": project_id},
        {"$set": update_data}
    )
    
    # Return updated project
    updated_project = await db.projects.find_one({"id": project_id})
    return Project(**updated_project)


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: User = Depends(get_current_user)):
    # Only staff can delete projects
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can delete projects")
    
    # Check if project exists
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if there are documents associated with this project
    documents_count = await db.documents.count_documents({"project_id": project_id})
    if documents_count > 0:
        # Delete all documents associated with this project
        await db.documents.delete_many({"project_id": project_id})
        logger.info(f"Deleted {documents_count} documents associated with project {project_id}")
        
        # Also clean up any uploaded files (optional, depends on your file storage strategy)
        import glob
        project_upload_path = f"/app/backend/uploads/{project_id}/*"
        files_to_delete = glob.glob(project_upload_path)
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete file {file_path}: {e}")
    
    # Delete any processing tasks associated with this project
    await db.process_tasks.delete_many({"project_id": project_id})
    
    # Delete the project
    result = await db.projects.delete_one({"id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"message": "Project deleted successfully", "project_id": project_id, "deleted_documents": documents_count}

# Initialize default admin user and test client
@api_router.post("/init/admin")
async def create_admin_user():
    # Check if admin already exists
    admin_exists = await db.users.find_one({"email": "admin@pergaminos.com"})
    if admin_exists:
        return {"message": "Admin user already exists"}
    
    # Create admin user
    admin_user = User(
        email="admin@pergaminos.com",
        name="Admin Pergaminos",
        role="staff"
    )
    
    user_doc = admin_user.dict()
    user_doc["hashed_password"] = get_password_hash("admin123")
    await db.users.insert_one(user_doc)
    
    return {"message": "Admin user created successfully", "email": "admin@pergaminos.com", "password": "admin123"}

# ============================================================================
# PDF MANAGER ENDPOINTS - PHASE 1: PLANNING
# ============================================================================

def fix_duplicate_target_names(plan: PDFManagerPlan) -> PDFManagerPlan:
    """
    Fix duplicate target names in rename operations by adding incremental suffixes.
    For example: file.pdf, file.pdf, file.pdf -> file.pdf, file_2.pdf, file_3.pdf
    """
    from collections import Counter
    
    # Count occurrences of each target name
    target_names = [op.to_name for op in plan.rename_operations]
    name_counts = Counter(target_names)
    
    # Find duplicates
    duplicates = {name for name, count in name_counts.items() if count > 1}
    
    if not duplicates:
        return plan  # No duplicates, return as-is
    
    # Track how many times we've seen each duplicate name
    seen_counts = {}
    
    # Fix duplicates by adding suffixes
    for op in plan.rename_operations:
        if op.to_name in duplicates:
            if op.to_name not in seen_counts:
                seen_counts[op.to_name] = 1
            else:
                seen_counts[op.to_name] += 1
                
                # Add suffix to make it unique
                base_name, ext = op.to_name.rsplit('.', 1) if '.' in op.to_name else (op.to_name, '')
                op.to_name = f"{base_name}_{seen_counts[op.to_name]}.{ext}" if ext else f"{base_name}_{seen_counts[op.to_name]}"
                op.reasoning += f" (Renamed to avoid duplicate)"
    
    # Add warning to validation
    if duplicates:
        plan.validation.warnings.append(
            f"Fixed {len(duplicates)} duplicate filename(s) by adding numeric suffixes"
        )
    
    return plan


async def generate_pdf_plan_with_ai(
    project: dict,
    company: dict,
    documents: List[dict],
    instruction: str
) -> PDFManagerPlan:
    """
    Generate a plan for PDF renaming and reordering using AI (GPT-4o).
    Extracts content from PDFs when needed for intelligent naming.
    Returns a plan with rename operations, reorder sequence, and validation.
    """
    try:
        # Get AI configuration for document processing
        ai_config = await get_ai_config_for_task(project["id"], "document_processing")
        
        # Check if instruction requires reading PDF content
        content_keywords = ["número de factura", "numero de factura", "invoice number", "número", "numero", 
                          "fecha", "date", "nombre", "name", "contenido", "content", "dentro del pdf", 
                          "detecte", "busque", "encuentre", "extraiga"]
        needs_content = any(keyword in instruction.lower() for keyword in content_keywords)
        
        # Prepare documents metadata for LLM
        docs_metadata = []
        for idx, doc in enumerate(documents):
            # Extract relevant metadata
            metadata = {
                "id": doc["id"],
                "name": doc["original_filename"],
                "uploaded_at": doc.get("created_at", "").isoformat() if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", "")),
            }
            
            # Add extracted data if available
            if doc.get("extracted_data"):
                extracted = doc["extracted_data"]
                if isinstance(extracted, dict):
                    metadata["extracted_data"] = {
                        k: v for k, v in extracted.items() 
                        if k in ["date", "client", "document_type", "amount", "invoice_number", "project_name"]
                    }
            
            # Extract PDF content if instruction requires it (only first 2 pages for performance)
            if needs_content and doc.get("file_path"):
                try:
                    logger.info(f"Extracting content from PDF {doc['original_filename']} for intelligent naming")
                    pdf_content = await extract_text_from_pdf_with_ocr(
                        doc["file_path"],
                        project_id=project["id"],
                        start_page=0,
                        max_pages=2  # Only read first 2 pages for naming
                    )
                    # Limit content to first 1000 characters to avoid token overflow
                    metadata["content_preview"] = pdf_content[:1000] if pdf_content else "[No text extracted]"
                except Exception as e:
                    logger.warning(f"Failed to extract content from {doc['original_filename']}: {str(e)}")
                    metadata["content_preview"] = "[Error extracting content]"
            
            docs_metadata.append(metadata)
        
        # Build LLM prompt with enhanced instructions
        system_prompt = """You are an expert document management AI planner. Your task is to analyze natural language instructions and generate a deterministic plan for renaming and reordering PDF documents.

You can extract specific data from PDF content (when provided in content_preview) to create intelligent file names.

RULES:
1. Return ONLY valid JSON, no markdown or explanations.
2. Use content_preview when available to extract specific data (invoice numbers, dates, names, etc.) for renaming.
3. If content_preview is provided, analyze it to find the requested data (e.g., "número de factura", "fecha", etc.).
4. For rename operations, use the document ID in "from_id" and generate a safe filename in "to_name".
5. Generate descriptive filenames based on extracted data: e.g., "Factura_12345.pdf", "Contrato_2024-01-15.pdf"
6. Preserve file extensions (.pdf).
7. For reordering, ALWAYS provide "reorder_ids" array with ALL document IDs in the desired order.
8. If no specific order is mentioned, maintain current order in reorder_ids.
9. Detect conflicts: duplicate names, missing required metadata, ambiguous instructions.
10. Set confidence (0.0-1.0) based on instruction clarity and data availability.
11. Use SAFE filenames: no special characters, spaces replaced with underscores.

OUTPUT FORMAT (MANDATORY):
{
  "rename_operations": [
    {"from_id": "doc_id", "from_name": "current.pdf", "to_name": "new_name_based_on_content.pdf", "reasoning": "Extracted invoice number 12345 from content"}
  ],
  "reorder_ids": ["doc_id_1", "doc_id_2", "doc_id_3"],
  "validation": {
    "confidence": 0.95,
    "conflicts": [],
    "warnings": []
  }
}

EXAMPLES:
- Instruction: "Renombrar PDFs según número de factura"
  Content: "FACTURA No. 12345"
  Result: "Factura_12345.pdf"

- Instruction: "Usar fecha del documento"
  Content: "Fecha: 15/01/2024"
  Result: "Documento_2024-01-15.pdf"

IMPORTANT: 
- reorder_ids MUST contain ALL document IDs
- If you can't find the requested data in content_preview, use a generic name with index
- Ensure all generated filenames are UNIQUE"""

        user_prompt = f"""CONTEXT:
Company: {company.get('name', 'N/A')}
Project: {project.get('name', 'N/A')}

INSTRUCTION:
{instruction}

DOCUMENTS METADATA:
{json.dumps(docs_metadata, indent=2, default=str)}

Generate the plan:"""

        # Create AI chat using configuration
        chat = await create_ai_chat_with_config(
            ai_config,
            f"pdf_plan_{project['id']}_{datetime.now().timestamp()}",
            system_prompt
        )
        
        from emergentintegrations.llm.chat import UserMessage
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        # Parse response - handle both string and object responses
        if isinstance(response, str):
            response_text = response.strip()
        elif hasattr(response, 'text'):
            response_text = response.text.strip()
        elif hasattr(response, 'content'):
            response_text = response.content.strip()
        else:
            # Try to convert to string
            response_text = str(response).strip()
        
        logger.info(f"LLM Response (first 200 chars): {response_text[:200]}")
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        plan_data = json.loads(response_text)
        
        # Validate and convert to Pydantic models
        rename_ops = [
            RenameOperation(
                from_id=op["from_id"],
                from_name=op["from_name"],
                to_name=op["to_name"],
                reasoning=op.get("reasoning", None)
            ) for op in plan_data.get("rename_operations", [])
        ]
        
        # Get reorder_ids from plan or default to all document IDs in current order
        reorder_ids = plan_data.get("reorder_ids", [])
        if not reorder_ids:
            # Default: keep current order or use order from rename operations
            reorder_ids = [doc["id"] for doc in documents]
            logger.info(f"No reorder_ids in plan, using default order with {len(reorder_ids)} documents")
        
        validation = PlanValidation(
            confidence=plan_data.get("validation", {}).get("confidence", 0.5),
            conflicts=plan_data.get("validation", {}).get("conflicts", []),
            warnings=plan_data.get("validation", {}).get("warnings", [])
        )
        
        plan = PDFManagerPlan(
            rename_operations=rename_ops,
            reorder_ids=reorder_ids,
            validation=validation
        )
        
        # Fix duplicate target names by adding incremental suffixes
        plan = fix_duplicate_target_names(plan)
        
        return plan
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
        logger.error(f"Response text: {response_text}")
        raise HTTPException(
            status_code=500,
            detail=f"AI generated invalid response format. Please try rephrasing your instruction."
        )
    except Exception as e:
        logger.error(f"Error generating PDF plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@api_router.post("/projects/{project_id}/pdf-manager/plan")
async def create_pdf_plan(
    project_id: str,
    plan_request: PDFManagerPlanRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Phase 1: Generate a plan for PDF renaming/reordering using AI.
    Does not modify files, only returns the plan for preview.
    """
    try:
        # Verify project exists and user has access
        project = await db.projects.find_one({"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Verify access
        company = await db.companies.find_one({"id": project["company_id"]})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if current_user.role == "client" and current_user.company_id != project["company_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get documents for this project
        documents = await db.documents.find({
            "project_id": project_id,
            "status": {"$in": ["completed", "processed", "qa_passed"]}
        }).to_list(10000)
        
        if not documents:
            raise HTTPException(
                status_code=400,
                detail="No processed documents found in this project"
            )
        
        logger.info(f"Generating PDF plan for project {project_id} with {len(documents)} documents")
        
        # Generate plan using AI
        plan = await generate_pdf_plan_with_ai(
            project, company, documents, plan_request.instruction
        )
        
        # Create job record
        job = PDFManagerJob(
            company_id=project["company_id"],
            project_id=project_id,
            instruction=plan_request.instruction,
            plan=plan,
            status="plan_ready",
            created_by=current_user.id,
            logs=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "plan_generated",
                "details": f"Generated plan with {len(plan.rename_operations)} rename operations and {len(plan.reorder_ids)} documents to reorder"
            }]
        )
        
        # Save job to database
        await db.pdf_manager_jobs.insert_one(job.dict())
        
        logger.info(f"PDF plan created successfully. Job ID: {job.id}")
        
        return {
            "job_id": job.id,
            "status": job.status,
            "plan": job.plan.dict(),
            "documents_count": len(documents),
            "created_at": job.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating PDF plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/projects/{project_id}/pdf-manager/jobs/{job_id}")
async def get_pdf_manager_job(
    project_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get details of a PDF Manager job (plan and execution status)"""
    try:
        # Find job
        job = await db.pdf_manager_jobs.find_one({"id": job_id, "project_id": project_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Verify access
        project = await db.projects.find_one({"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        company = await db.companies.find_one({"id": project["company_id"]})
        if current_user.role == "client" and current_user.company_id != project["company_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Convert ObjectId to string if present
        if "_id" in job:
            del job["_id"]
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching PDF manager job: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/projects/{project_id}/pdf-manager/jobs")
async def list_pdf_manager_jobs(
    project_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """List all PDF Manager jobs for a project"""
    try:
        # Verify access
        project = await db.projects.find_one({"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        company = await db.companies.find_one({"id": project["company_id"]})
        if current_user.role == "client" and current_user.company_id != project["company_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get jobs
        jobs = await db.pdf_manager_jobs.find(
            {"project_id": project_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Clean up jobs
        for job in jobs:
            if "_id" in job:
                del job["_id"]
        
        return {
            "project_id": project_id,
            "jobs": jobs,
            "total": len(jobs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing PDF manager jobs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/pdf-manager/download/zip/{job_id}")
async def download_zip(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Download ZIP file for a completed job"""
    try:
        # Find job
        job = await db.pdf_manager_jobs.find_one({"id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Verify access to project
        project = await db.projects.find_one({"id": job["project_id"]})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        company = await db.companies.find_one({"id": project["company_id"]})
        if current_user.role == "client" and current_user.company_id != project["company_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get ZIP path from job
        if not job.get("result_urls") or not job["result_urls"].get("zip_filename"):
            raise HTTPException(status_code=404, detail="ZIP file not found for this job")
        
        zip_filename = job["result_urls"]["zip_filename"]
        zip_path = UPLOAD_DIR / "pdf_manager_output" / zip_filename
        
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail=f"ZIP file does not exist: {zip_filename}")
        
        from fastapi.responses import FileResponse as FR
        return FR(
            path=str(zip_path),
            filename=zip_filename,
            media_type="application/zip"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading ZIP: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/pdf-manager/download/file/{job_id}/{file_name:path}")
async def download_file(
    job_id: str,
    file_name: str,
    current_user: User = Depends(get_current_user)
):
    """Download individual PDF file from a completed job"""
    import urllib.parse
    
    # Decode URL-encoded filename
    decoded_filename = urllib.parse.unquote(file_name)
    logger.info(f"Downloading file: {decoded_filename} from job {job_id}")
    
    # Find job
    job = await db.pdf_manager_jobs.find_one({"id": job_id})
    if not job:
        logger.error(f"Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify access to project
    project = await db.projects.find_one({"id": job["project_id"]})
    if not project:
        logger.error(f"Project not found: {job['project_id']}")
        raise HTTPException(status_code=404, detail="Project not found")
    
    company = await db.companies.find_one({"id": project["company_id"]})
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get file path
    file_path = UPLOAD_DIR / "pdf_manager_temp" / job_id / decoded_filename
    
    logger.info(f"Looking for file at: {file_path}")
    logger.info(f"File exists: {file_path.exists()}")
    
    if not file_path.exists():
        # Try listing directory to see what's there
        dir_path = UPLOAD_DIR / "pdf_manager_temp" / job_id
        if dir_path.exists():
            files = list(dir_path.iterdir())
            logger.error(f"File not found. Available files in directory: {[f.name for f in files]}")
        else:
            logger.error(f"Directory does not exist: {dir_path}")
        raise HTTPException(status_code=404, detail=f"File does not exist: {decoded_filename}")
    
    # Return file with proper headers using FileResponse
    from fastapi.responses import FileResponse as FR
    return FR(
        path=str(file_path),
        filename=decoded_filename,
        media_type="application/pdf"
    )

# ============================================================================
# PDF MANAGER - PHASE 2: EXECUTION
# ============================================================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters and ensure safety.
    Preserves extension.
    """
    # Split name and extension
    if '.' in filename:
        name_part, ext = filename.rsplit('.', 1)
        ext = f".{ext}"
    else:
        name_part = filename
        ext = ""
    
    # Remove invalid characters
    import re
    name_part = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name_part)
    
    # Collapse multiple spaces
    name_part = re.sub(r'\s+', ' ', name_part)
    
    # Trim whitespace
    name_part = name_part.strip()
    
    # Limit length (max 200 chars for name, keeping extension)
    if len(name_part) > 200:
        name_part = name_part[:200]
    
    # Ensure not empty
    if not name_part:
        name_part = "document"
    
    return name_part + ext


async def validate_plan_for_execution(
    plan: PDFManagerPlan,
    documents: List[dict]
) -> tuple[bool, List[str]]:
    """
    Validate plan before execution.
    Returns (is_valid, list_of_errors)
    """
    errors = []
    
    # Create document ID map
    doc_map = {doc["id"]: doc for doc in documents}
    
    # Validate all document IDs exist
    for op in plan.rename_operations:
        if op.from_id not in doc_map:
            errors.append(f"Document ID {op.from_id} not found in project")
    
    for doc_id in plan.reorder_ids:
        if doc_id not in doc_map:
            errors.append(f"Document ID {doc_id} in reorder list not found in project")
    
    # Check for duplicate target names
    target_names = [op.to_name for op in plan.rename_operations]
    duplicates = [name for name in target_names if target_names.count(name) > 1]
    if duplicates:
        errors.append(f"Duplicate target names found: {', '.join(set(duplicates))}")
    
    # Check that all documents are in reorder list
    if len(plan.reorder_ids) != len(documents):
        errors.append(f"Reorder list has {len(plan.reorder_ids)} documents but project has {len(documents)}")
    
    return len(errors) == 0, errors


async def apply_renames_and_generate_zip(
    job: PDFManagerJob,
    documents: List[dict],
    plan: PDFManagerPlan
) -> Dict[str, Any]:
    """
    Apply rename operations to files and database, then generate ordered ZIP.
    Returns result_urls dict with file URLs and zip URL.
    """
    try:
        import shutil
        import zipfile
        from pathlib import Path
        
        # Create a temporary directory for processed files (use UPLOAD_DIR which is already defined)
        temp_dir = UPLOAD_DIR / "pdf_manager_temp" / job.id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create output directory for ZIP
        output_dir = UPLOAD_DIR / "pdf_manager_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get project and company info for history
        project = await db.projects.find_one({"id": job.project_id})
        company = await db.companies.find_one({"id": project["company_id"]}) if project else None
        
        # Get user info
        user = await db.users.find_one({"id": job.created_by})
        user_name = user.get("name", "Unknown") if user else "Unknown"
        
        # Map document IDs to documents
        doc_map = {doc["id"]: doc for doc in documents}
        
        # Map of old name to new name from plan
        rename_map = {op.from_id: op.to_name for op in plan.rename_operations}
        
        # Step 1: Copy and rename files to temp directory
        renamed_files = []
        for doc_id in documents:
            doc = doc_map.get(doc_id["id"])
            if not doc:
                continue
            
            original_path = Path(doc["file_path"])
            if not original_path.exists():
                logger.warning(f"File not found: {original_path}")
                continue
            
            # Get new name from plan or keep original
            new_name = rename_map.get(doc["id"], doc["original_filename"])
            new_name = sanitize_filename(new_name)
            
            # Copy file to temp directory with new name
            temp_file_path = temp_dir / new_name
            shutil.copy2(original_path, temp_file_path)
            
            renamed_files.append({
                "id": doc["id"],
                "original_name": doc["original_filename"],
                "new_name": new_name,
                "temp_path": str(temp_file_path),
                "size": original_path.stat().st_size
            })
            
            # Update document in database with new name
            await db.documents.update_one(
                {"id": doc["id"]},
                {
                    "$set": {
                        "original_filename": new_name,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "processing_history": {
                            "action": "renamed_by_pdf_manager",
                            "old_name": doc["original_filename"],
                            "new_name": new_name,
                            "job_id": job.id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            )
            
            # Save to PDF history for each renamed file
            if company and project and new_name != doc["original_filename"]:
                import urllib.parse
                encoded_filename = urllib.parse.quote(new_name)
                download_url = f"/api/pdf-manager/download/file/{job.id}/{encoded_filename}"
                
                await save_pdf_history(
                    company_id=company["id"],
                    company_name=company.get("name", "Unknown"),
                    project_id=job.project_id,
                    project_name=project.get("name", "Unknown"),
                    operation_type="rename",
                    original_pdf_name=doc["original_filename"],
                    result_pdf_name=new_name,
                    result_pdf_path=str(temp_file_path),
                    instruction=job.instruction,
                    job_id=job.id,
                    performed_by=job.created_by,
                    performed_by_name=user_name,
                    download_url=download_url
                )
        
        # Step 2: Create ordered ZIP according to plan.reorder_ids
        zip_filename = f"reordered_pdfs_{job.project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = output_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add files in the order specified by plan
            for idx, doc_id in enumerate(plan.reorder_ids, 1):
                # Find the renamed file info
                file_info = next((f for f in renamed_files if f["id"] == doc_id), None)
                if not file_info:
                    logger.warning(f"Document {doc_id} not found in renamed files")
                    continue
                
                # Add prefix to maintain order when extracted
                ordered_name = f"{idx:03d}_{file_info['new_name']}"
                
                # Add to ZIP
                zipf.write(file_info["temp_path"], ordered_name)
        
        # Step 3: Generate URLs using API endpoints for reliable downloads
        import urllib.parse
        file_urls = []
        for file_info in renamed_files:
            encoded_filename = urllib.parse.quote(file_info['new_name'])
            file_urls.append({
                "id": file_info["id"],
                "name": file_info["new_name"],
                "original_name": file_info["original_name"],
                "url": f"/api/pdf-manager/download/file/{job.id}/{encoded_filename}",
                "size": file_info["size"]
            })
        
        result_urls = {
            "files": file_urls,
            "zip_url": f"/api/pdf-manager/download/zip/{job.id}",
            "zip_size": zip_path.stat().st_size,
            "zip_filename": zip_filename,
            "total_files": len(file_urls),
            "job_id": job.id
        }
        
        # Cleanup: Remove temp directory after a delay (optional, or keep for downloads)
        # Can implement cleanup job later
        
        return result_urls
        
    except Exception as e:
        logger.error(f"Error applying renames and generating ZIP: {str(e)}", exc_info=True)
        raise


@api_router.post("/projects/{project_id}/pdf-manager/execute")
async def execute_pdf_plan(
    project_id: str,
    request_body: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Phase 2: Execute a PDF Manager plan.
    Applies renames, updates DB, generates ordered ZIP.
    """
    try:
        job_id = request_body.get("job_id")
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required")
        
        # Find job
        job_doc = await db.pdf_manager_jobs.find_one({"id": job_id, "project_id": project_id})
        if not job_doc:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = PDFManagerJob(**job_doc)
        
        # Verify job is in correct state
        if job.status != "plan_ready":
            if job.status == "completed":
                # Idempotent: return existing results
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "result_urls": job.result_urls,
                    "message": "Plan already executed"
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Job is not ready for execution. Current status: {job.status}"
                )
        
        # Verify access
        project = await db.projects.find_one({"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        company = await db.companies.find_one({"id": project["company_id"]})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check permissions - only staff and asesor can execute
        if current_user.role == "client":
            raise HTTPException(status_code=403, detail="Clients cannot execute plans. Contact your asesor or admin.")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get current documents
        documents = await db.documents.find({
            "project_id": project_id,
            "status": {"$in": ["completed", "processed", "qa_passed"]}
        }).to_list(10000)
        
        if not documents:
            raise HTTPException(status_code=400, detail="No documents found in project")
        
        # Validate plan against current state
        is_valid, validation_errors = await validate_plan_for_execution(job.plan, documents)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Plan validation failed: {'; '.join(validation_errors)}"
            )
        
        # Update job status to executing
        await db.pdf_manager_jobs.update_one(
            {"id": job_id},
            {
                "$set": {"status": "executing", "updated_at": datetime.now(timezone.utc)},
                "$push": {
                    "logs": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event": "execution_started",
                        "user": current_user.email,
                        "details": f"Starting execution of {len(job.plan.rename_operations)} renames and reordering {len(job.plan.reorder_ids)} documents"
                    }
                }
            }
        )
        
        logger.info(f"Executing PDF Manager plan for job {job_id}")
        
        # Apply renames and generate ZIP
        result_urls = await apply_renames_and_generate_zip(job, documents, job.plan)
        
        # Update job with results
        await db.pdf_manager_jobs.update_one(
            {"id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "result_urls": result_urls,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "logs": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event": "execution_completed",
                        "user": current_user.email,
                        "details": f"Successfully processed {result_urls['total_files']} files. ZIP size: {result_urls['zip_size']} bytes"
                    }
                }
            }
        )
        
        logger.info(f"PDF Manager plan executed successfully. Job ID: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "result_urls": result_urls,
            "message": "Plan executed successfully"
        }
        
    except HTTPException as e:
        # Update job status to failed if it was being executed
        if 'job_id' in locals() and job_id:
            await db.pdf_manager_jobs.update_one(
                {"id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": str(e.detail),
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "logs": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "event": "execution_failed",
                            "error": str(e.detail)
                        }
                    }
                }
            )
        raise
    except Exception as e:
        logger.error(f"Error executing PDF plan: {str(e)}", exc_info=True)
        
        # Update job status to failed
        if 'job_id' in locals() and job_id:
            await db.pdf_manager_jobs.update_one(
                {"id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": str(e),
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "logs": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "event": "execution_failed",
                            "error": str(e)
                        }
                    }
                }
            )
        
        raise HTTPException(status_code=500, detail=str(e))


# ========== PDF PAGE MANAGER ENDPOINTS ==========

def parse_page_range(range_str: str, total_pages: int) -> List[int]:
    """
    Parse manual page range string into list of page numbers.
    Examples: "1-20" -> [1,2,3...20], "1,5,10" -> [1,5,10], "1-10,15,20-25" -> [1,2...10,15,20,21...25]
    """
    pages = []
    parts = range_str.replace(" ", "").split(",")
    
    for part in parts:
        if "-" in part:
            # Range like "1-20"
            start, end = part.split("-")
            try:
                start_page = int(start)
                end_page = int(end)
                if start_page < 1 or end_page > total_pages:
                    raise ValueError(f"Page range {start}-{end} is out of bounds (1-{total_pages})")
                pages.extend(range(start_page, end_page + 1))
            except ValueError as e:
                raise ValueError(f"Invalid range format: {part}. {str(e)}")
        else:
            # Single page like "5"
            try:
                page = int(part)
                if page < 1 or page > total_pages:
                    raise ValueError(f"Page {page} is out of bounds (1-{total_pages})")
                pages.append(page)
            except ValueError as e:
                raise ValueError(f"Invalid page number: {part}. {str(e)}")
    
    # Remove duplicates and sort
    return sorted(list(set(pages)))

async def generate_pdf_extract_plan_with_ai(
    project: dict,
    pdf_filename: str,
    pdf_path: str,
    instruction: str,
    manual_range: Optional[str] = None
) -> PDFPageExtractPlan:
    """
    Generate a plan for extracting specific pages from a PDF.
    Can use AI to interpret instruction or manual range.
    """
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        # If manual range provided, use it directly
        if manual_range:
            try:
                pages_to_extract = parse_page_range(manual_range, total_pages)
                return PDFPageExtractPlan(
                    pdf_filename=pdf_filename,
                    total_pages=total_pages,
                    pages_to_extract=pages_to_extract,
                    new_filename=f"{Path(pdf_filename).stem}_extracted.pdf",
                    confidence=1.0,
                    reasoning=f"Extracción manual de páginas: {manual_range}"
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # Use AI to interpret natural language instruction
        ai_config = await get_ai_config_for_task(project["id"], "data_extraction")
        
        # Create AI chat
        chat = await create_ai_chat_with_config(
            ai_config,
            f"pdf_extract_{pdf_filename}",
            "Eres un experto en procesamiento de PDFs. Interpreta instrucciones para extraer páginas específicas."
        )
        
        prompt = f"""Analiza esta instrucción para extraer páginas de un PDF:

PDF: {pdf_filename}
Total de páginas: {total_pages}
Instrucción: {instruction}

Determina qué páginas deben extraerse basándote en la instrucción.

REGLAS:
1. Devuelve SOLO JSON válido
2. Los números de página empiezan en 1
3. Proporciona razonamiento claro EN ESPAÑOL

FORMATO OBLIGATORIO:
{{
  "pages_to_extract": [1, 2, 3, ...],
  "new_filename": "nombre_descriptivo.pdf",
  "confidence": 0.95,
  "reasoning": "Explicación de por qué estas páginas"
}}

Ejemplos:
- "Extraer primeras 20 páginas" -> pages_to_extract: [1,2,3...20]
- "Solo páginas impares" -> pages_to_extract: [1,3,5,7...]
- "Páginas 10 a 50" -> pages_to_extract: [10,11,12...50]
"""
        
        from emergentintegrations.llm.chat import UserMessage
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse JSON
        import json, re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            raise ValueError("AI did not return valid JSON")
        
        result = json.loads(json_match.group())
        
        # Validate pages
        pages_to_extract = result.get("pages_to_extract", [])
        if not pages_to_extract:
            raise ValueError("No pages specified for extraction")
        
        # Filter invalid pages
        pages_to_extract = [p for p in pages_to_extract if 1 <= p <= total_pages]
        
        if not pages_to_extract:
            raise ValueError("All specified pages are out of range")
        
        return PDFPageExtractPlan(
            pdf_filename=pdf_filename,
            total_pages=total_pages,
            pages_to_extract=sorted(pages_to_extract),
            new_filename=result.get("new_filename", f"{Path(pdf_filename).stem}_extracted.pdf"),
            confidence=result.get("confidence", 0.8),
            reasoning=result.get("reasoning", "Páginas extraídas según instrucción")
        )
        
    except Exception as e:
        logger.error(f"Error generating extract plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al generar plan de extracción: {str(e)}")

async def generate_pdf_page_plan_with_ai(
    project: dict,
    pdf_filename: str,
    pdf_path: str,
    instruction: str
) -> PDFPagePlan:
    """
    Generate a plan for reordering pages within a single PDF using AI.
    Uses OCR (Tesseract) as fallback for scanned PDFs without embedded text.
    """
    try:
        # Get AI configuration - use data_extraction config since it's the same for document processing
        ai_config = await get_ai_config_for_task(project["id"], "data_extraction")
        
        # Get PDF metadata and extract text from each page
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        # Extract text from each page
        pages_content = []
        total_text_extracted = 0
        
        for page_num in range(total_pages):
            try:
                page = reader.pages[page_num]
                
                # Try multiple extraction methods
                text = ""
                
                # Method 1: Standard extraction
                try:
                    text = page.extract_text() or ""
                except:
                    pass
                
                # Method 2: Try with layout mode if available
                if not text or len(text.strip()) < 10:
                    try:
                        text = page.extract_text(extraction_mode="layout") or ""
                    except:
                        pass
                
                # Clean up text
                text = text.strip()
                
                # Log for debugging
                if text and len(text) > 0:
                    total_text_extracted += len(text)
                    logger.info(f"Page {page_num + 1}: Extracted {len(text)} characters")
                else:
                    logger.warning(f"Page {page_num + 1}: No text extracted")
                
                # Truncate text to first 800 characters for better context
                text_preview = text[:800] if text else ""
                
                pages_content.append({
                    "page_number": page_num + 1,
                    "text_preview": text_preview,
                    "has_text": len(text) > 0
                })
                
            except Exception as e:
                logger.error(f"Error extracting text from page {page_num + 1}: {str(e)}", exc_info=True)
                pages_content.append({
                    "page_number": page_num + 1,
                    "text_preview": "",
                    "has_text": False
                })
        
        logger.info(f"Total text extracted from PDF: {total_text_extracted} characters across {total_pages} pages")
        
        # If no text was extracted, try OCR on a sample of pages
        if total_text_extracted < 50 and total_pages > 0:
            logger.info(f"PDF appears to be scanned (no embedded text). Attempting OCR on sample pages...")
            
            try:
                import pytesseract
                from pdf2image import convert_from_path
                from PIL import Image
                
                # Determine how many pages to OCR (sample strategy)
                # For large PDFs, only OCR first 10, middle, and last pages
                pages_to_ocr = []
                if total_pages <= 10:
                    pages_to_ocr = list(range(total_pages))
                else:
                    # First 5, middle 3, last 2
                    pages_to_ocr = list(range(5))  # First 5
                    middle = total_pages // 2
                    pages_to_ocr.extend([middle - 1, middle, middle + 1])  # Middle 3
                    pages_to_ocr.extend([total_pages - 2, total_pages - 1])  # Last 2
                    pages_to_ocr = sorted(set(pages_to_ocr))  # Remove duplicates and sort
                
                logger.info(f"OCR will process {len(pages_to_ocr)} pages out of {total_pages}")
                
                # Convert specific pages to images
                images = convert_from_path(
                    pdf_path,
                    first_page=1,
                    last_page=min(max(pages_to_ocr) + 1, total_pages),
                    dpi=200  # Lower DPI for speed
                )
                
                ocr_success_count = 0
                for idx in pages_to_ocr:
                    try:
                        if idx < len(images):
                            # Perform OCR with Spanish language
                            ocr_text = pytesseract.image_to_string(
                                images[idx],
                                lang='spa',
                                config='--psm 6'  # Assume uniform block of text
                            ).strip()
                            
                            if ocr_text and len(ocr_text) > 20:
                                pages_content[idx]["text_preview"] = ocr_text[:800]
                                pages_content[idx]["has_text"] = True
                                total_text_extracted += len(ocr_text)
                                ocr_success_count += 1
                                logger.info(f"OCR Page {idx + 1}: Extracted {len(ocr_text)} characters")
                            else:
                                logger.warning(f"OCR Page {idx + 1}: Minimal text extracted")
                    except Exception as ocr_error:
                        logger.error(f"OCR failed for page {idx + 1}: {str(ocr_error)}")
                
                logger.info(f"OCR completed: {ocr_success_count} pages processed successfully. Total text now: {total_text_extracted} characters")
                
            except Exception as ocr_setup_error:
                logger.error(f"OCR setup failed: {str(ocr_setup_error)}", exc_info=True)
                # Continue without OCR
        
        # Build LLM prompt
        system_prompt = """Eres un experto en gestión de páginas PDF con IA. Tu tarea es analizar el contenido de las páginas de un PDF y generar un plan para reordenarlas según instrucciones en lenguaje natural.

REGLAS:
1. Devuelve SOLO JSON válido, sin markdown ni explicaciones.
2. Los números de página empiezan en 1 (la primera página es 1, no 0).
3. Analiza el contenido de texto de cada página para tomar decisiones informadas.
4. Si una página no tiene texto extraíble (puede ser una imagen o escaneo), indícalo en el razonamiento.
5. Genera una secuencia completa que incluya TODAS las páginas.
6. Proporciona un razonamiento claro EN ESPAÑOL explicando qué páginas identificaste y por qué.
7. Establece la confianza (0.0-1.0) basándote en qué tan bien encontraste el contenido mencionado en las instrucciones.
8. Si no puedes encontrar el contenido solicitado, propón un orden lógico y explica por qué.

FORMATO DE SALIDA (OBLIGATORIO):
{
  "new_page_sequence": [3, 1, 2, 4, 5],
  "confidence": 0.95,
  "reasoning": "Encontré 'notas importantes' en la página 3, la moví a la segunda posición como se solicitó. La página 1 permanece primero, la página 2 se movió a la tercera posición."
}

IMPORTANTE: 
- new_page_sequence DEBE contener TODOS los números de página (1 a total_pages) exactamente una vez.
- Si el PDF contiene principalmente imágenes sin texto extraíble, menciona esto en el razonamiento.
- Busca palabras clave, nombres, fechas, títulos, o cualquier texto distintivo mencionado en las instrucciones."""

        # Count pages with text
        pages_with_text = sum(1 for p in pages_content if p.get('has_text', False))
        
        # Build pages content section with better formatting
        pages_info = "\n\n".join([
            f"PÁGINA {page['page_number']} {'(CON TEXTO)' if page.get('has_text') else '(SIN TEXTO EXTRAÍBLE)'}:\n{page['text_preview']}"
            for page in pages_content
        ])

        user_prompt = f"""ARCHIVO PDF: {pdf_filename}
TOTAL DE PÁGINAS: {total_pages}
PÁGINAS CON TEXTO EXTRAÍBLE: {pages_with_text} de {total_pages}

CONTENIDO DE LAS PÁGINAS:
{pages_info}

INSTRUCCIÓN:
{instruction}

NOTA: Analiza cuidadosamente el contenido de texto extraído de cada página. Si algunas páginas no tienen texto, pueden ser imágenes escaneadas o páginas gráficas. Busca palabras clave, nombres, títulos o cualquier contenido que coincida con la instrucción.

Analiza el contenido anterior y genera el plan de reordenamiento:"""

        # Create AI chat
        chat = await create_ai_chat_with_config(
            ai_config,
            f"pdf_page_plan_{project['id']}_{datetime.now().timestamp()}",
            system_prompt
        )
        
        from emergentintegrations.llm.chat import UserMessage
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        # Parse response
        if isinstance(response, str):
            response_text = response.strip()
        elif hasattr(response, 'text'):
            response_text = response.text.strip()
        elif hasattr(response, 'content'):
            response_text = response.content.strip()
        else:
            response_text = str(response).strip()
        
        logger.info(f"LLM Page Reorder Response: {response_text[:200]}")
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        plan_data = json.loads(response_text)
        
        # Validate the plan
        new_sequence = plan_data.get("new_page_sequence", [])
        if len(new_sequence) != total_pages:
            raise ValueError(f"Plan must include all {total_pages} pages. Got {len(new_sequence)} pages.")
        
        if set(new_sequence) != set(range(1, total_pages + 1)):
            raise ValueError("Plan must contain each page number exactly once.")
        
        # Create page reorder operations
        reorder_operations = []
        for idx, page_num in enumerate(new_sequence):
            if page_num != idx + 1:  # Only add if position changed
                reorder_operations.append(PageReorderOperation(
                    page_number=page_num,
                    new_position=idx + 1
                ))
        
        # Create plan
        plan = PDFPagePlan(
            pdf_filename=pdf_filename,
            total_pages=total_pages,
            reorder_operations=reorder_operations,
            new_page_sequence=new_sequence,
            confidence=plan_data.get("confidence", 0.8),
            reasoning=plan_data.get("reasoning", "Page reordering based on instructions")
        )
        
        return plan
        
    except Exception as e:
        logger.error(f"Error generating PDF page plan: {str(e)}", exc_info=True)
        raise


async def execute_pdf_page_reorder(
    job: PDFPageManagerJob,
    source_pdf_path: str
) -> str:
    """
    Execute page reordering on a PDF and save the result.
    Returns the path to the new PDF.
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
        
        # Create output directory
        output_dir = UPLOAD_DIR / "pdf_page_reorder_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Read source PDF
        reader = PdfReader(source_pdf_path)
        writer = PdfWriter()
        
        # Add pages in new order
        for page_num in job.plan.new_page_sequence:
            # PyPDF2 uses 0-indexed pages internally
            writer.add_page(reader.pages[page_num - 1])
        
        # Generate output filename
        base_name = Path(job.pdf_filename).stem
        output_filename = f"{base_name}_reordered_{job.id[:8]}.pdf"
        output_path = output_dir / output_filename
        
        # Write output PDF
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        logger.info(f"PDF page reordering completed: {output_path}")
        
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error executing PDF page reorder: {str(e)}", exc_info=True)
        raise

async def execute_pdf_page_extract(
    extract_plan: PDFPageExtractPlan,
    source_pdf_path: str,
    job_id: str
) -> str:
    """
    Execute page extraction from a PDF and save as new PDF.
    Returns the path to the new PDF.
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
        
        # Create output directory
        output_dir = UPLOAD_DIR / "pdf_page_extract_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Read source PDF
        reader = PdfReader(source_pdf_path)
        writer = PdfWriter()
        
        # Add specified pages
        for page_num in extract_plan.pages_to_extract:
            # PyPDF2 uses 0-indexed pages internally
            writer.add_page(reader.pages[page_num - 1])
        
        # Generate output filename
        output_filename = f"{Path(extract_plan.new_filename).stem}_{job_id[:8]}.pdf"
        output_path = output_dir / output_filename
        
        # Write output PDF
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        logger.info(f"PDF page extraction completed: {output_path}, {len(extract_plan.pages_to_extract)} pages extracted")
        
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error executing PDF page extract: {str(e)}", exc_info=True)
        raise


@api_router.post("/projects/{project_id}/pdf-page-manager/plan")
async def create_pdf_page_plan(
    project_id: str,
    plan_request: PDFPageManagerPlanRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate a plan for reordering or extracting pages from a specific PDF.
    Supports two modes: 'reorder' (reorganize pages) or 'extract' (create new PDF with specific pages).
    """
    try:
        # Verify project exists and user has access
        project = await db.projects.find_one({"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Verify access
        company = await db.companies.find_one({"id": project["company_id"]})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if current_user.role == "client" and current_user.company_id != project["company_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Find the document
        document = await db.documents.find_one({
            "project_id": project_id,
            "original_filename": plan_request.pdf_filename,
            "status": {"$in": ["completed", "processed", "qa_passed"]}
        })
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"PDF '{plan_request.pdf_filename}' not found in project"
            )
        
        # Get PDF file path
        pdf_path = Path(document["file_path"])
        logger.info(f"Looking for PDF at: {pdf_path} (absolute: {pdf_path.resolve()})")
        logger.info(f"PDF path exists: {pdf_path.exists()}")
        
        if not pdf_path.exists():
            # Try to find the file in the upload directory
            filename = Path(document["file_path"]).name
            alternative_path = UPLOAD_DIR / filename
            logger.info(f"Trying alternative path: {alternative_path}")
            
            if alternative_path.exists():
                logger.info(f"Found PDF at alternative location: {alternative_path}")
                pdf_path = alternative_path
                # Update document path in database
                await db.documents.update_one(
                    {"id": document["id"]},
                    {"$set": {"file_path": str(alternative_path)}}
                )
            else:
                logger.error(f"PDF not found at {pdf_path} or {alternative_path}")
                logger.error(f"Upload directory contents: {list(UPLOAD_DIR.glob('*')) if UPLOAD_DIR.exists() else 'Directory not found'}")
                raise HTTPException(
                    status_code=404,
                    detail=f"PDF file not found on server. Searched in: {pdf_path} and {alternative_path}"
                )
        
        logger.info(f"Generating PDF page plan for {plan_request.pdf_filename}, mode: {plan_request.mode}")
        
        # Generate plan based on mode
        if plan_request.mode == "extract":
            # Extract mode - create new PDF with specific pages
            extract_plan = await generate_pdf_extract_plan_with_ai(
                project,
                plan_request.pdf_filename,
                str(pdf_path),
                plan_request.instruction,
                plan_request.manual_range
            )
            
            # Create job record for extract
            job = PDFPageManagerJob(
                company_id=project["company_id"],
                project_id=project_id,
                pdf_filename=plan_request.pdf_filename,
                instruction=plan_request.instruction,
                mode="extract",
                plan=None,
                extract_plan=extract_plan,
                status="plan_ready",
                created_by=current_user.id,
                logs=[{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "extract_plan_generated",
                    "details": f"Plan to extract {len(extract_plan.pages_to_extract)} pages from {extract_plan.total_pages} total pages"
                }]
            )
            
            # Save job
            await db.pdf_page_manager_jobs.insert_one(job.dict())
            
            return {
                "job_id": job.id,
                "mode": "extract",
                "plan": extract_plan.dict(),
                "status": "plan_ready"
            }
        
        else:
            # Reorder mode - reorganize pages within the PDF
            plan = await generate_pdf_page_plan_with_ai(
                project,
                plan_request.pdf_filename,
                str(pdf_path),
                plan_request.instruction
            )
            
            # Create job record
            job = PDFPageManagerJob(
                company_id=project["company_id"],
                project_id=project_id,
                pdf_filename=plan_request.pdf_filename,
                instruction=plan_request.instruction,
                mode="reorder",
                plan=plan,
                extract_plan=None,
                status="plan_ready",
                created_by=current_user.id,
                logs=[{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "plan_generated",
                    "details": f"Generated plan to reorder {plan.total_pages} pages"
                }]
            )
            
            # Save job to database
            await db.pdf_page_manager_jobs.insert_one(job.dict())
            
            logger.info(f"PDF page plan created successfully. Job ID: {job.id}")
            
            return {
                "job_id": job.id,
                "mode": "reorder",
                "status": job.status,
                "plan": job.plan.dict(),
                "created_at": job.created_at.isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating PDF page plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/projects/{project_id}/pdf-page-manager/execute")
async def execute_pdf_page_plan(
    project_id: str,
    request_body: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Execute a PDF page reordering plan.
    """
    try:
        job_id = request_body.get("job_id")
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required")
        
        # Find job
        job_doc = await db.pdf_page_manager_jobs.find_one({"id": job_id, "project_id": project_id})
        if not job_doc:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = PDFPageManagerJob(**job_doc)
        
        # Verify job is in correct state
        if job.status != "plan_ready":
            if job.status == "completed":
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "result_url": job.result_url,
                    "result_filename": job.result_filename,
                    "message": "Plan already executed"
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Job is not ready for execution. Current status: {job.status}"
                )
        
        # Verify access
        project = await db.projects.find_one({"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        company = await db.companies.find_one({"id": project["company_id"]})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check permissions - only staff and asesor can execute
        if current_user.role == "client":
            raise HTTPException(status_code=403, detail="Clients cannot execute plans. Contact your asesor or admin.")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Find source document
        document = await db.documents.find_one({
            "project_id": project_id,
            "original_filename": job.pdf_filename
        })
        
        if not document:
            raise HTTPException(status_code=404, detail="Source PDF not found")
        
        # file_path is stored as absolute path, so use it directly
        pdf_path = Path(document["file_path"])
        logger.info(f"Execute: Looking for PDF at: {pdf_path} (absolute: {pdf_path.resolve()})")
        logger.info(f"Execute: PDF path exists: {pdf_path.exists()}")
        
        if not pdf_path.exists():
            # Try to find the file in the upload directory
            filename = Path(document["file_path"]).name
            alternative_path = UPLOAD_DIR / filename
            logger.info(f"Execute: Trying alternative path: {alternative_path}")
            
            if alternative_path.exists():
                logger.info(f"Execute: Found PDF at alternative location: {alternative_path}")
                pdf_path = alternative_path
                # Update document path in database
                await db.documents.update_one(
                    {"id": document["id"]},
                    {"$set": {"file_path": str(alternative_path)}}
                )
            else:
                logger.error(f"Execute: PDF not found at {pdf_path} or {alternative_path}")
                logger.error(f"Execute: Upload directory: {UPLOAD_DIR}")
                logger.error(f"Execute: Upload directory exists: {UPLOAD_DIR.exists()}")
                if UPLOAD_DIR.exists():
                    logger.error(f"Execute: Upload directory contents: {list(UPLOAD_DIR.glob('*'))[:10]}")  # Show first 10 files
                raise HTTPException(
                    status_code=404,
                    detail=f"PDF file not found on server. Searched in: {pdf_path} and {alternative_path}"
                )
        
        # Update job status to executing
        await db.pdf_page_manager_jobs.update_one(
            {"id": job_id},
            {
                "$set": {"status": "executing", "updated_at": datetime.now(timezone.utc)},
                "$push": {
                    "logs": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event": "execution_started",
                        "user": current_user.email
                    }
                }
            }
        )
        
        logger.info(f"Executing PDF page operation ({job.mode}) for job {job_id}")
        
        # Execute based on mode
        if job.mode == "extract":
            # Execute extraction
            if not job.extract_plan:
                raise HTTPException(status_code=400, detail="Extract plan not found in job")
            output_path = await execute_pdf_page_extract(job.extract_plan, str(pdf_path), job_id)
            operation_type = "extracción"
        else:
            # Execute reordering
            if not job.plan:
                raise HTTPException(status_code=400, detail="Reorder plan not found in job")
            output_path = await execute_pdf_page_reorder(job, str(pdf_path))
            operation_type = "reordenamiento"
        
        # Generate download URL
        output_filename = Path(output_path).name
        result_url = f"/api/pdf-page-manager/download/{job_id}/{output_filename}"
        
        # Update job with results
        await db.pdf_page_manager_jobs.update_one(
            {"id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "result_url": result_url,
                    "result_filename": output_filename,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "logs": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event": "execution_completed",
                        "user": current_user.email
                    }
                }
            }
        )
        
        logger.info(f"PDF page {operation_type} completed successfully. Job ID: {job_id}")
        
        # Save to PDF history
        history_operation_type = "extract" if job.mode == "extract" else "reorder"
        await save_pdf_history(
            company_id=company["id"],
            company_name=company.get("name", "Unknown"),
            project_id=project_id,
            project_name=project.get("name", "Unknown"),
            operation_type=history_operation_type,
            original_pdf_name=job.pdf_filename,
            result_pdf_name=output_filename,
            result_pdf_path=output_path,
            instruction=job.instruction,
            job_id=job_id,
            performed_by=current_user.id,
            performed_by_name=current_user.name,
            download_url=result_url
        )
        
        return {
            "job_id": job_id,
            "status": "completed",
            "result_url": result_url,
            "result_filename": output_filename,
            "message": f"Operación de {operation_type} completada exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Update job status to failed
        if 'job_id' in locals() and job_id:
            await db.pdf_page_manager_jobs.update_one(
                {"id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": str(e),
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "logs": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "event": "execution_failed",
                            "error": str(e)
                        }
                    }
                }
            )
        
        logger.error(f"Error executing PDF page plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/pdf-page-manager/download/{job_id}/{file_name:path}")
async def download_reordered_pdf(
    job_id: str,
    file_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Download a reordered or extracted PDF file (authenticated).
    """
    try:
        # Find job
        job = await db.pdf_page_manager_jobs.find_one({"id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Verify access
        project = await db.projects.find_one({"id": job["project_id"]})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        company = await db.companies.find_one({"id": project["company_id"]})
        if current_user.role == "client" and current_user.company_id != project["company_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor" and company.get("asesor_comercial_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get file path based on mode
        mode = job.get("mode", "reorder")
        if mode == "extract":
            output_dir = UPLOAD_DIR / "pdf_page_extract_output"
        else:
            output_dir = UPLOAD_DIR / "pdf_page_reorder_output"
        
        file_path = output_dir / file_name
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        # Stream file
        def iterfile():
            with open(file_path, mode="rb") as file:
                yield from file
        
        return StreamingResponse(
            iterfile(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={file_name}",
                "Content-Type": "application/pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading reordered PDF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== PDF HISTORY ENDPOINTS ==========

async def save_pdf_history(
    company_id: str,
    company_name: str,
    project_id: str,
    project_name: str,
    operation_type: str,
    original_pdf_name: str,
    result_pdf_name: str,
    result_pdf_path: str,
    instruction: Optional[str],
    job_id: str,
    performed_by: str,
    performed_by_name: str,
    download_url: str
):
    """Helper function to save PDF operation history"""
    try:
        # Create history directory if it doesn't exist
        history_dir = Path("pdf_history")
        history_dir.mkdir(exist_ok=True)
        
        # Create subdirectory by company and project
        company_dir = history_dir / company_id / project_id
        company_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the PDF to permanent history location
        source_path = Path(result_pdf_path)
        permanent_path = None
        file_size = None
        page_count = None
        
        if source_path.exists():
            # Create unique filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{result_pdf_name}"
            permanent_path = company_dir / unique_filename
            
            # Copy file to permanent location
            shutil.copy2(source_path, permanent_path)
            logger.info(f"PDF copied to history: {permanent_path}")
            
            # Get file size and page count
            file_size = permanent_path.stat().st_size
            try:
                from PyPDF2 import PdfReader
                pdf_reader = PdfReader(str(permanent_path))
                page_count = len(pdf_reader.pages)
            except Exception as e:
                logger.warning(f"Could not get page count: {str(e)}")
        else:
            logger.warning(f"Source file not found for history: {source_path}")
            permanent_path = source_path  # Use original path as fallback
        
        history_entry = PDFHistory(
            company_id=company_id,
            company_name=company_name,
            project_id=project_id,
            project_name=project_name,
            operation_type=operation_type,
            original_pdf_name=original_pdf_name,
            result_pdf_name=result_pdf_name,
            result_pdf_path=str(permanent_path),
            instruction=instruction,
            job_id=job_id,
            performed_by=performed_by,
            performed_by_name=performed_by_name,
            file_size=file_size,
            page_count=page_count,
            download_url=download_url
        )
        
        await db.pdf_history.insert_one(history_entry.dict())
        logger.info(f"PDF history saved: {operation_type} - {result_pdf_name}")
        
    except Exception as e:
        logger.error(f"Error saving PDF history: {str(e)}", exc_info=True)
        # Don't raise exception, history is not critical


@api_router.get("/pdf-history")
async def get_pdf_history(
    company_id: Optional[str] = None,
    project_id: Optional[str] = None,
    operation_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get PDF history with filters.
    Staff and asesor can filter by company/project.
    Clients can only see their company's history.
    """
    try:
        # Build query filter
        query_filter = {}
        
        # Apply role-based filtering
        if current_user.role == "client":
            # Get all companies the client has access to
            accessible_company_ids = set()
            
            # Add from company_ids list
            if current_user.company_ids:
                accessible_company_ids.update(current_user.company_ids)
            
            # Add backward compatibility for single company_id
            if current_user.company_id:
                accessible_company_ids.add(current_user.company_id)
            
            # Add companies from assigned corporation
            if current_user.assigned_corporation:
                corp_companies = await db.companies.find(
                    {"corporacion": current_user.assigned_corporation}
                ).to_list(1000)
                accessible_company_ids.update([c["id"] for c in corp_companies])
            
            if not accessible_company_ids:
                raise HTTPException(status_code=403, detail="Client user has no companies assigned")
            
            # Filter to accessible companies
            if company_id:
                # Verify client has access to this specific company
                if company_id not in accessible_company_ids:
                    raise HTTPException(status_code=403, detail="Access denied to this company")
                query_filter["company_id"] = company_id
            else:
                query_filter["company_id"] = {"$in": list(accessible_company_ids)}
        elif current_user.role == "asesor":
            # Asesores can only see their assigned companies' history
            assigned_companies = await db.companies.find(
                {"asesor_comercial_id": current_user.id, "is_active": True}
            ).to_list(None)
            company_ids = [c["id"] for c in assigned_companies]
            if company_id:
                # Verify asesor has access to this company
                if company_id not in company_ids:
                    raise HTTPException(status_code=403, detail="Access denied to this company")
                query_filter["company_id"] = company_id
            else:
                # Filter to only assigned companies
                query_filter["company_id"] = {"$in": company_ids}
        else:
            # Staff can see all, apply optional filters
            if company_id:
                query_filter["company_id"] = company_id
        
        # Apply additional filters
        if project_id:
            query_filter["project_id"] = project_id
        
        if operation_type:
            query_filter["operation_type"] = operation_type
        
        # Get history entries sorted by most recent first
        history_entries = await db.pdf_history.find(query_filter).sort("performed_at", -1).to_list(None)
        
        # Remove MongoDB's _id field from all entries
        for entry in history_entries:
            if '_id' in entry:
                del entry['_id']
        
        # Apply retention policy filter
        retention_config = await db.retention_policy.find_one({"id": "global_retention_policy"})
        if retention_config:
            retention_months = retention_config.get("retention_months", 6)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_months * 30)
            
            # Filter out old entries - handle both timezone-aware and naive datetimes
            filtered_entries = []
            for entry in history_entries:
                performed_at = entry.get("performed_at")
                if performed_at:
                    # If performed_at is naive (no timezone), assume UTC
                    if performed_at.tzinfo is None:
                        performed_at = performed_at.replace(tzinfo=timezone.utc)
                    
                    if performed_at > cutoff_date:
                        filtered_entries.append(entry)
            
            history_entries = filtered_entries
        
        return {
            "history": history_entries,
            "total": len(history_entries)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PDF history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/pdf-history/download/{history_id}")
async def download_pdf_from_history(
    history_id: str,
    current_user: User = Depends(get_current_user)
):
    """Download a PDF from history"""
    try:
        # Find history entry
        history_entry = await db.pdf_history.find_one({"id": history_id})
        if not history_entry:
            raise HTTPException(status_code=404, detail="History entry not found")
        
        # Verify access
        if current_user.role == "client":
            if current_user.company_id != history_entry["company_id"]:
                raise HTTPException(status_code=403, detail="Access denied")
        elif current_user.role == "asesor":
            company = await db.companies.find_one({"id": history_entry["company_id"]})
            if company.get("asesor_comercial_id") != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Get file path
        file_path = Path(history_entry["result_pdf_path"])
        
        if not file_path.exists():
            logger.error(f"File not found in history: {file_path}")
            raise HTTPException(status_code=404, detail="File not found. It may have been deleted.")
        
        # Stream file
        def iterfile():
            with open(file_path, mode="rb") as file:
                yield from file
        
        return StreamingResponse(
            iterfile(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={history_entry['result_pdf_name']}",
                "Content-Type": "application/pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading PDF from history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/pdf-history/download-batch")
async def download_batch_pdfs_from_history(
    history_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    """Download multiple PDFs from history as a ZIP file"""
    try:
        logger.info(f"Batch download request from user {current_user.email} for {len(history_ids)} files")
        
        if not history_ids:
            raise HTTPException(status_code=400, detail="No history IDs provided")
        
        if len(history_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 files can be downloaded at once")
        
        # Collect valid files
        files_to_zip = []
        not_found_count = 0
        access_denied_count = 0
        missing_file_count = 0
        
        for history_id in history_ids:
            history_entry = await db.pdf_history.find_one({"id": history_id})
            if not history_entry:
                logger.warning(f"History entry not found: {history_id}")
                not_found_count += 1
                continue
            
            # Verify access
            if current_user.role == "client":
                if current_user.company_id != history_entry["company_id"]:
                    logger.warning(f"Access denied for client to history: {history_id}")
                    access_denied_count += 1
                    continue
            elif current_user.role == "asesor":
                company = await db.companies.find_one({"id": history_entry["company_id"]})
                if company and company.get("asesor_comercial_id") != current_user.id:
                    logger.warning(f"Access denied for asesor to history: {history_id}")
                    access_denied_count += 1
                    continue
            
            # Check if file exists
            file_path = Path(history_entry["result_pdf_path"])
            logger.info(f"Checking file path: {file_path}")
            if file_path.exists():
                files_to_zip.append({
                    "path": file_path,
                    "name": history_entry["result_pdf_name"]
                })
                logger.info(f"File found and added: {history_entry['result_pdf_name']}")
            else:
                logger.warning(f"File not found at path: {file_path}")
                missing_file_count += 1
        
        logger.info(f"Batch download summary: {len(files_to_zip)} valid, {not_found_count} not found, {access_denied_count} access denied, {missing_file_count} files missing")
        
        if not files_to_zip:
            error_msg = f"No valid files found. History entries not found: {not_found_count}, Access denied: {access_denied_count}, Files missing: {missing_file_count}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_info in files_to_zip:
                # Add file to ZIP with its name
                zip_file.write(file_info["path"], arcname=file_info["name"])
        
        zip_buffer.seek(0)
        
        # Generate filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"historial_pdfs_{timestamp}.zip"
        
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}",
                "Content-Type": "application/zip"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating batch download: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@api_router.delete("/pdf-history/{history_id}")
async def delete_pdf_from_history(
    history_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a PDF from history (staff only)"""
    try:
        # Only staff can delete from history
        if current_user.role != "staff":
            raise HTTPException(status_code=403, detail="Solo el staff puede eliminar del historial")
        
        # Find history entry
        history_entry = await db.pdf_history.find_one({"id": history_id})
        if not history_entry:
            raise HTTPException(status_code=404, detail="Entrada de historial no encontrada")
        
        # Delete the history entry from database
        result = await db.pdf_history.delete_one({"id": history_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar la entrada")
        
        # Optionally delete the physical file (commented out for safety - files might be in use)
        # file_path = Path(history_entry["result_pdf_path"])
        # if file_path.exists():
        #     try:
        #         file_path.unlink()
        #         logger.info(f"Deleted file: {file_path}")
        #     except Exception as e:
        #         logger.warning(f"Could not delete file {file_path}: {str(e)}")
        
        logger.info(f"Deleted history entry {history_id} by {current_user.email}")
        
        return {
            "message": "Entrada eliminada del historial exitosamente",
            "history_id": history_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting PDF from history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/retention-policy")
async def get_retention_policy(current_user: User = Depends(get_current_user)):
    """Get retention policy configuration"""
    try:
        config = await db.retention_policy.find_one({"id": "global_retention_policy"})
        if not config:
            # Return default
            return {
                "retention_months": 6,
                "updated_at": None,
                "updated_by": None
            }
        return config
    except Exception as e:
        logger.error(f"Error getting retention policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/retention-policy")
async def update_retention_policy(
    update: RetentionPolicyUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update retention policy (admin only)"""
    try:
        # Only staff can update retention policy
        if current_user.role != "staff":
            raise HTTPException(status_code=403, detail="Only staff can update retention policy")
        
        # Validate retention_months
        if update.retention_months not in [6, 12]:
            raise HTTPException(status_code=400, detail="retention_months must be 6 or 12")
        
        # Update or create retention policy
        config = RetentionPolicyConfig(
            retention_months=update.retention_months,
            updated_by=current_user.id
        )
        
        await db.retention_policy.update_one(
            {"id": "global_retention_policy"},
            {"$set": config.dict()},
            upsert=True
        )
        
        logger.info(f"Retention policy updated to {update.retention_months} months by {current_user.email}")
        
        return {
            "message": "Retention policy updated successfully",
            "retention_months": update.retention_months
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating retention policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== USER MANUAL ENDPOINTS ==========

async def get_first_active_project_ai_config():
    """Get AI configuration from the first active project that has one"""
    try:
        # Find first active project with AI configuration
        projects = await db.projects.find({"status": "active"}).to_list(100)
        
        for project in projects:
            # Try to get data_extraction config
            config = await db.ai_configurations.find_one({
                "project_id": project["id"],
                "config_type": "data_extraction",
                "is_active": True
            })
            
            if config and config.get("api_key"):
                logger.info(f"Found AI config from project {project['id']}")
                try:
                    decrypted_key = decrypt_api_key(config["api_key"])
                    if decrypted_key and len(decrypted_key) > 10:
                        return {
                            "provider": config["provider"],
                            "api_key": decrypted_key,
                            "model_name": config["model_name"],
                            "model_config": config.get("model_parameters", {}),
                            "source": f"project_{project['id']}"
                        }
                except Exception as e:
                    logger.warning(f"Failed to decrypt key from project {project['id']}: {str(e)}")
                    continue
        
        # Fallback to Emergent LLM key
        logger.info("No project AI config found, using Emergent LLM key")
        return {
            "provider": "emergent",
            "api_key": os.environ.get('EMERGENT_LLM_KEY'),
            "model_name": "gpt-4o",
            "model_config": {},
            "source": "fallback_emergent"
        }
        
    except Exception as e:
        logger.error(f"Error getting AI config: {str(e)}", exc_info=True)
        return {
            "provider": "emergent",
            "api_key": os.environ.get('EMERGENT_LLM_KEY'),
            "model_name": "gpt-4o",
            "model_config": {},
            "source": "error_fallback"
        }


@api_router.post("/manual/chat")
async def manual_chat(
    request_body: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Chat endpoint for user manual assistance.
    Only accessible by staff and asesor roles.
    """
    try:
        # Check permissions
        if current_user.role not in ["staff", "asesor"]:
            raise HTTPException(
                status_code=403,
                detail="Solo staff y asesores pueden acceder al asistente del manual"
            )
        
        question = request_body.get("question", "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="La pregunta es requerida")
        
        # Get AI configuration
        ai_config = await get_first_active_project_ai_config()
        
        # System prompt with manual context
        system_prompt = """Eres un asistente experto del sistema "Pergaminos - Sistema de Digitalización Inteligente". Tu trabajo es ayudar a los usuarios a entender y usar la plataforma.

MÓDULOS DEL SISTEMA:

1. **Dashboard**: Vista general con estadísticas de empresas, proyectos, documentos procesados, QA aprobados/fallidos, etc. Incluye filtros de fecha.

2. **Empresas**: Gestión de empresas cliente. Puedes crear, editar y filtrar empresas por corporación y estado (Activa/Inactiva). Soporta múltiples contactos por empresa. Campos: nombre, contactos (nombre, email, teléfono), asesor comercial, segmento/industria, corporación, dirección.

3. **Proyectos**: Gestión de proyectos de digitalización por empresa. Cada proyecto tiene nombre, código alfanumérico único, descripción, estado (activo/completado) e instrucciones semánticas para la IA. Filtros por empresa y corporación.

4. **Documentos (dentro de Proyectos)**: Sube PDFs para procesamiento (límite: 500MB/archivo, 1GB/lote). El sistema realiza QA automático y extracción de datos con IA. Estados: subido, QA en proceso, QA aprobado/fallado, procesando (con mensajes de progreso en tiempo real), completado. Muestra barra de progreso y mensajes como "🔍 Extrayendo texto con OCR...", "🤖 Extrayendo datos...".

5. **PDF Manager IA**: Renombra y reordena PDFs de un proyecto usando lenguaje natural. Genera un plan, lo previsualizas, y lo ejecutas. Descarga ZIP con archivos renombrados y reordenados.

6. **PDF Manager IA por Página**: Dos modos:
   - **Reordenar Páginas**: Reorganiza el orden de páginas dentro de un PDF
   - **Extraer Páginas**: Crea nuevo PDF con páginas específicas (rangos manuales "1-20" o lenguaje natural "extraer primeras 20 páginas")

7. **Agentes QA**: Configura reglas de calidad para validar PDFs antes de procesarlos. Ejemplo: "verificar que tenga fecha", "debe contener palabra clave X". Los hallazgos se reportan en español.

8. **Hallazgos QA**: Visualiza documentos que fallaron QA y requieren revisión manual.

9. **Datos Extraídos**: Consulta toda la información extraída por IA de los PDFs procesados (fechas, montos, nombres, etc.).

10. **Segmentos**: Define segmentos de industria para clasificar empresas (Tecnología, Salud, Finanzas, etc.).

11. **Configuración IA**: Configura API keys de OpenAI por proyecto para los tres procesos: Extracción de datos, Agente QA, y Reordenamiento/Renombrado. Solo soporta OpenAI como proveedor.

12. **Configuración OCR Global**: Dos métodos para extraer texto de PDFs escaneados:
    - **Tesseract OCR**: Gratis y rápido, ideal para documentos simples
    - **GPT-4o Vision**: Máxima precisión, usa tokens OpenAI, ~7 seg/página, ideal para documentos complejos o mala calidad

13. **Usuarios**: Gestión de usuarios del sistema. Roles: 
    - Staff (administrador): Acceso completo, puede resetear contraseñas
    - Asesor: Asignado a empresas específicas
    - Cliente: Acceso de solo lectura a su empresa

INSTRUCCIONES:
- **IMPORTANTE: Responde SIEMPRE en el MISMO IDIOMA en que el usuario hace la pregunta**
- Si pregunta en español, responde en español
- Si pregunta en inglés, responde en inglés
- Sé claro, conciso y útil
- Si no sabes algo, admítelo
- Proporciona ejemplos cuando sea posible
- Si la pregunta es ambigua, pide aclaración en el idioma de la pregunta"""

        user_prompt = f"""User question: {question}

Please provide a clear and helpful answer in the same language as the question."""

        # Create AI chat
        chat = await create_ai_chat_with_config(
            ai_config,
            f"manual_chat_{current_user.id}_{datetime.now().timestamp()}",
            system_prompt
        )
        
        from emergentintegrations.llm.chat import UserMessage
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        # Parse response
        if isinstance(response, str):
            response_text = response.strip()
        elif hasattr(response, 'text'):
            response_text = response.text.strip()
        elif hasattr(response, 'content'):
            response_text = response.content.strip()
        else:
            response_text = str(response).strip()
        
        logger.info(f"Manual chat - User: {current_user.email}, Question: {question[:50]}")
        
        return {
            "answer": response_text,
            "question": question
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/manual/download-pdf")
async def download_manual_pdf(current_user: User = Depends(get_current_user)):
    """
    Generate and download the user manual as PDF.
    Only accessible by staff and asesor roles.
    """
    try:
        # Check permissions
        if current_user.role not in ["staff", "asesor"]:
            raise HTTPException(
                status_code=403,
                detail="Solo staff y asesores pueden descargar el manual"
            )
        
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from io import BytesIO
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Centered', alignment=TA_CENTER, fontSize=24, spaceAfter=30))
        styles.add(ParagraphStyle(name='SectionTitle', fontSize=16, spaceAfter=12, spaceBefore=12, textColor='darkblue'))
        styles.add(ParagraphStyle(name='Subsection', fontSize=14, spaceAfter=8, spaceBefore=8, textColor='darkgreen'))
        
        # Title
        elements.append(Paragraph("Manual de Usuario", styles['Centered']))
        elements.append(Paragraph("Sistema Pergaminos", styles['Centered']))
        elements.append(Paragraph("Digitalización Inteligente", styles['Centered']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Content sections
        manual_content = [
            {
                "title": "1. Dashboard",
                "content": "Vista general del sistema que muestra estadísticas clave: número total de empresas, proyectos, documentos procesados, documentos en proceso, documentos fallidos, revisión de QA, QA aprobados, QA fallidos y QA pendientes. Proporciona accesos rápidos a las funciones principales del sistema."
            },
            {
                "title": "2. Empresas",
                "content": "Módulo de gestión de empresas cliente. Permite crear nuevas empresas, editarlas, ver sus proyectos y aplicar filtros por corporación y estado (Activa/Inactiva). Campos disponibles: nombre, email, teléfono, asesor comercial asignado, segmento/industria, corporación y dirección. Las empresas inactivas no permiten login de sus usuarios."
            },
            {
                "title": "3. Proyectos",
                "content": "Gestión de proyectos de digitalización asociados a cada empresa. Cada proyecto contiene documentos PDF que serán procesados. Puedes crear proyectos con nombre, descripción, estado (activo/completado) e instrucciones semánticas para guiar a la IA en el procesamiento. Incluye tres pestañas: Documentos, PDF Manager IA y PDF Manager IA por Página."
            },
            {
                "title": "4. Subir y Procesar Documentos",
                "content": "Dentro de cada proyecto, sube archivos PDF (hasta 10 simultáneos). El sistema ejecuta automáticamente: 1) Control de calidad (QA) según las reglas configuradas, 2) Extracción de datos con IA si pasa QA. Estados del documento: subido, QA en proceso, QA aprobado/fallido, procesando con IA, completado o necesita revisión manual."
            },
            {
                "title": "5. PDF Manager IA",
                "content": "Herramienta para renombrar y reordenar múltiples PDFs de un proyecto usando lenguaje natural. Proceso: 1) Escribe instrucción (ej: 'Renombrar con formato Empresa-Fecha-Tipo'), 2) La IA genera un plan, 3) Previsualizas los cambios, 4) Ejecutas el plan, 5) Descargas ZIP con archivos procesados y archivos individuales."
            },
            {
                "title": "6. PDF Manager IA por Página",
                "content": "Reordena páginas DENTRO de un PDF específico. Proceso: 1) Selecciona un PDF del proyecto, 2) Escribe instrucción (ej: 'Mover página con notas importantes al inicio'), 3) La IA analiza el contenido de cada página, 4) Genera plan con nuevo orden, 5) Ejecutas y descargas el PDF reordenado."
            },
            {
                "title": "7. Agentes QA",
                "content": "Configura reglas de control de calidad para validar PDFs antes del procesamiento con IA. Define condiciones que los documentos deben cumplir, como presencia de fechas, palabras clave, formato correcto, etc. Evita procesar documentos de baja calidad."
            },
            {
                "title": "8. Hallazgos QA",
                "content": "Visualiza todos los documentos que fallaron el control de calidad automático y requieren revisión manual. Muestra los hallazgos específicos detectados por los agentes QA para cada documento."
            },
            {
                "title": "9. Datos Extraídos",
                "content": "Consulta centralizada de toda la información extraída por IA de los PDFs procesados. Incluye fechas, montos, nombres de clientes, tipos de documento, números de factura, etc. Permite búsqueda y filtrado de datos."
            },
            {
                "title": "10. Segmentos",
                "content": "Define y gestiona segmentos de industria para clasificar empresas. Ejemplos: Tecnología Avanzada, Salud, Finanzas, Retail, etc. Útil para organizar clientes y generar reportes segmentados."
            },
            {
                "title": "11. Configuración IA",
                "content": "Configura las API keys de OpenAI a nivel de proyecto. Tres tipos de configuración independientes: 1) Extracción de datos, 2) Agente QA, 3) Reordenamiento y renombrado. Selecciona empresa → proyecto → modelo → API key. Las claves se encriptan antes de almacenarse."
            },
            {
                "title": "12. Usuarios",
                "content": "Gestión de usuarios del sistema. Tres roles disponibles: Staff (administrador con acceso completo), Asesor (asignado a empresas específicas, acceso limitado a sus clientes), Cliente (acceso solo a su empresa y proyectos). El usuario admin@pergaminos.com no puede ser eliminado."
            },
            {
                "title": "Notas Importantes",
                "content": "- Las empresas inactivas bloquean el acceso de sus usuarios. - Los PDFs deben pasar QA antes de procesarse con IA. - Las API keys se encriptan para seguridad. - El sistema soporta procesamiento paralelo de múltiples documentos. - Usa el chat del manual para preguntas específicas sobre el uso del sistema."
            }
        ]
        
        # Add content
        for section in manual_content:
            elements.append(Paragraph(section["title"], styles['SectionTitle']))
            elements.append(Paragraph(section["content"], styles['Normal']))
            elements.append(Spacer(1, 0.2*inch))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF value
        pdf_value = buffer.getvalue()
        buffer.close()
        
        # Return as streaming response
        return StreamingResponse(
            iter([pdf_value]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=Manual_Pergaminos.pdf",
                "Content-Type": "application/pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating manual PDF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# Mount static directories for PDF Manager outputs BEFORE including router
pdf_manager_temp_dir = UPLOAD_DIR / "pdf_manager_temp"
pdf_manager_output_dir = UPLOAD_DIR / "pdf_manager_output"
pdf_manager_temp_dir.mkdir(parents=True, exist_ok=True)
pdf_manager_output_dir.mkdir(parents=True, exist_ok=True)

app.mount("/uploads/pdf_manager_temp", StaticFiles(directory=str(pdf_manager_temp_dir)), name="pdf_manager_temp")
app.mount("/uploads/pdf_manager_output", StaticFiles(directory=str(pdf_manager_output_dir)), name="pdf_manager_output")

# Include the router in the main app
app.include_router(api_router)


# DEBUG ENDPOINT - Remove after fixing production issue
@api_router.get("/debug/user-model")
async def debug_user_model(current_user: User = Depends(get_current_user)):
    """Debug endpoint to check user model serialization"""
    try:
        return {
            "status": "ok",
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "role": current_user.role,
                "company_id": current_user.company_id,
                "company_ids": current_user.company_ids,
                "assigned_corporation": current_user.assigned_corporation,
                "is_active": current_user.is_active
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

@api_router.get("/debug/health")
async def debug_health():
    """Simple health check - no auth required"""
    try:
        # Test MongoDB connection
        await db.users.find_one({})
        return {
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()