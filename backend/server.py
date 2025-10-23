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
    return User(**user)

# Pydantic Models
class UserRole(BaseModel):
    role: str  # "staff", "asesor", or "client"

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str  # "staff", "asesor", or "client"
    company_id: Optional[str] = None  # Only for client users
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str  # "staff", "asesor", or "client"
    company_id: Optional[str] = None

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

class Company(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # Nombre comercial
    razon_social: Optional[str] = None
    nombre_comercial: Optional[str] = None  # Duplicado de name para claridad
    nit: Optional[str] = None
    description: Optional[str] = None
    contacto: Optional[str] = None  # Nombre del contacto
    contact_email: Optional[EmailStr] = None
    telefono: Optional[str] = None
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
    direccion: Optional[str] = None
    asesor_comercial_id: Optional[str] = None
    segmento: Optional[str] = None
    corporacion: Optional[str] = None
    is_active: Optional[bool] = True

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    company_id: str
    status: str = "active"  # active, completed, paused
    semantic_instructions: Optional[str] = None  # Instructions for AI processing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # user id

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    company_id: str
    semantic_instructions: Optional[str] = None

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
    # QA fields
    qa_status: Optional[str] = None  # pending, passed, failed, manual_review
    qa_results: Optional[Dict[str, Any]] = None  # QA agent results
    qa_findings: Optional[List[Dict[str, Any]]] = None  # Important findings for manual review
    qa_processed_at: Optional[datetime] = None
    qa_approved_by: Optional[str] = None  # Staff user who approved after manual review
    qa_approved_at: Optional[datetime] = None
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

class PDFPageManagerJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    project_id: str
    pdf_filename: str  # The specific PDF being processed
    instruction: str  # Natural language instruction
    plan: Optional[PDFPagePlan] = None
    status: str = "pending"  # pending, plan_ready, executing, completed, failed
    result_url: Optional[str] = None  # URL to download reordered PDF
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

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

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
    
    # Validate company_id for client users
    if user_data.role == "client" and user_data.company_id:
        company = await db.companies.find_one({"id": user_data.company_id})
        if not company:
            raise HTTPException(status_code=400, detail="Company not found")
    
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
    return company

@api_router.get("/companies", response_model=List[Company])
async def get_companies(current_user: User = Depends(get_current_user)):
    if current_user.role == "client" and current_user.company_id:
        # Clients can only see their own company
        companies = await db.companies.find({"id": current_user.company_id}).to_list(1000)
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
    if current_user.role == "client" and current_user.company_id != company_id:
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
    
    project_dict = project_data.dict()
    project_dict["created_by"] = current_user.id
    project = Project(**project_dict)
    
    await db.projects.insert_one(project.dict())
    return project

@api_router.get("/projects", response_model=List[Project])
async def get_projects(current_user: User = Depends(get_current_user)):
    if current_user.role == "client" and current_user.company_id:
        # Clients can only see projects from their company
        projects = await db.projects.find({"company_id": current_user.company_id}).to_list(1000)
    else:
        # Staff can see all projects
        projects = await db.projects.find().to_list(1000)
    
    return [Project(**project) for project in projects]

@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, current_user: User = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access permissions
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return Project(**project)

@api_router.get("/projects/{project_id}/documents", response_model=List[Document])
async def get_project_documents(project_id: str, current_user: User = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access permissions
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
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
    
    # Save file
    file_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    filename = f"{file_id}{file_extension}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
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
    
    # Validate all files are PDFs
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF. Only PDF files are supported")
    
    document_ids = []
    
    # Save all files first
    for file in files:
        # Save file
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        filename = f"{file_id}{file_extension}"
        file_path = UPLOAD_DIR / filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
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
        "message": f"Batch upload successful. {len(files)} documents uploaded.",
        "batch_task_id": batch_task.id,
        "document_ids": document_ids,
        "files_uploaded": len(files)
    }

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
        import PyPDF2
        
        # Get AI configuration for QA
        project = await db.projects.find_one({"id": document["project_id"]})
        company = await db.companies.find_one({"id": project["company_id"]})
        
        ai_config = await get_ai_config_for_task(document["project_id"], "qa_processing")
        if not ai_config.get("api_key"):
            return {"error": "No AI configuration available", "overall_score": 0}
        
        # Extract text from PDF for analysis
        # Note: emergentintegrations only supports file attachments with Gemini provider
        # For OpenAI, we extract text and send it in the prompt
        pdf_text = ""
        try:
            with open(document["file_path"], 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                total_pages = len(pdf_reader.pages)
                # Extract text from first 10 pages for QA (to avoid token limits)
                pages_to_extract = min(10, total_pages)
                for page_num in range(pages_to_extract):
                    page = pdf_reader.pages[page_num]
                    pdf_text += f"\n--- PAGE {page_num + 1} ---\n"
                    pdf_text += page.extract_text()
                
                if total_pages > pages_to_extract:
                    pdf_text += f"\n\n[Note: Document has {total_pages} total pages, analyzed first {pages_to_extract} pages]"
                    
        except Exception as e:
            logger.error(f"Error extracting PDF text for QA: {str(e)}")
            pdf_text = "[Error: Could not extract text from PDF]"
        
        all_results = []
        critical_findings = []
        
        for agent in qa_agents:
            try:
                # Create AI chat for QA using configured model
                chat = await create_ai_chat_with_config(
                    ai_config,
                    f"qa_{agent['id']}_{document_id}",
                    "You are a document quality assurance AI. Analyze documents for quality issues and provide detailed assessment."
                )
                
                # Create QA prompt
                quality_checks = agent.get("quality_checks", {})
                active_checks = [check for check, enabled in quality_checks.items() if enabled]
                
                prompt = f"""
                Analyze this document for quality assurance based on the following criteria:
                
                QA INSTRUCTIONS: {agent['qa_instructions']}
                
                QUALITY CHECKS TO PERFORM:
                {', '.join(active_checks) if active_checks else 'General document quality assessment'}
                
                DOCUMENT TEXT CONTENT:
                {pdf_text[:15000]}
                
                Please provide a JSON response with:
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
                            "category": "readability|completeness|structure|content|other",
                            "description": "Detailed description",
                            "location": "page number or section",
                            "recommendation": "How to fix"
                        }}
                    ],
                    "recommendation": "approve|manual_review|reject",
                    "summary": "Brief summary of assessment"
                }}
                
                Score 0-100 where:
                - 80-100: Excellent quality, approve automatically
                - 60-79: Good quality but may need review
                - 0-59: Poor quality, likely needs rejection or reprocessing
                
                Note: Visual quality checks (image clarity, orientation) require visual analysis which is not available with text-only processing.
                Focus on text readability, completeness, structure, and content quality.
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

async def process_single_chunk(file_path: str, semantic_instructions: str, ai_config: dict, chunk_number: int, start_page: int, end_page: int) -> dict:
    """Process a single PDF chunk with AI using configured model"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import PyPDF2
        
        # Extract text from specified pages of the PDF
        # Note: emergentintegrations only supports file attachments with Gemini provider
        # For OpenAI, we extract text and send it in the prompt
        pdf_text = ""
        try:
            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                # Extract text from the specified page range (0-indexed)
                for page_num in range(start_page - 1, min(end_page, len(pdf_reader.pages))):
                    page = pdf_reader.pages[page_num]
                    pdf_text += f"\n--- PAGE {page_num + 1} ---\n"
                    pdf_text += page.extract_text()
                    
        except Exception as e:
            logger.error(f"Error extracting PDF text for chunk {chunk_number}: {str(e)}")
            pdf_text = f"[Error: Could not extract text from PDF chunk {chunk_number}]"
        
        chat = await create_ai_chat_with_config(
            ai_config,
            f"chunk_processing_{chunk_number}_{start_page}_{end_page}",
            "You are an expert document analysis AI. Extract structured data from document chunks based on specific instructions."
        )
        
        prompt = f"""
        Analyze this PDF chunk (pages {start_page} to {end_page}) and extract structured data based on these instructions:
        
        {semantic_instructions}
        
        DOCUMENT TEXT CONTENT:
        {pdf_text}
        
        Please provide the extracted data in JSON format with clear field names and values.
        If certain information is not available, mark it as null.
        Focus on accuracy and completeness.
        
        Note: This is chunk {chunk_number} of a larger document. Extract all relevant data from these specific pages.
        """
        
        user_message = UserMessage(text=prompt)
        
        # Process with AI
        response = await chat.send_message(user_message)
        
        # Try to parse JSON from response
        import json
        import re
        
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                extracted_data = json.loads(json_match.group())
                return {
                    "chunk_number": chunk_number,
                    "start_page": start_page,
                    "end_page": end_page,
                    "data": extracted_data,
                    "status": "success"
                }
            except json.JSONDecodeError:
                return {
                    "chunk_number": chunk_number,
                    "start_page": start_page,
                    "end_page": end_page,
                    "raw_response": response,
                    "status": "needs_review"
                }
        else:
            return {
                "chunk_number": chunk_number,
                "start_page": start_page,
                "end_page": end_page,
                "raw_response": response,
                "status": "needs_review"
            }
            
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_number}: {str(e)}")
        return {
            "chunk_number": chunk_number,
            "start_page": start_page,
            "end_page": end_page,
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
                    "processing_progress": 0,
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
                
                # Create chunk file
                chunk_filename = f"{document_id}_chunk_{chunk_idx + 1}.pdf"
                chunk_path = Path(document["file_path"]).parent / chunk_filename
                
                if create_pdf_chunk(document["file_path"], start_page, end_page, str(chunk_path)):
                    # Get AI config for data extraction
                    extraction_config = await get_ai_config_for_task(project["id"], "data_extraction")
                    
                    # Process this chunk with AI
                    chunk_result = await process_single_chunk(
                        str(chunk_path), 
                        semantic_instructions, 
                        extraction_config,
                        chunk_idx + 1,
                        start_page + 1,
                        end_page + 1
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
            extraction_config = await get_ai_config_for_task(project["id"], "data_extraction")
            combined_data = await process_single_chunk(
                document["file_path"],
                semantic_instructions,
                extraction_config,
                1,
                1,
                total_pages
            )
        
        # Process and store extracted data in normalized format
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
                    "processing_progress": 100
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
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    if current_user.role == "staff":
        # Staff sees all stats
        companies_count = await db.companies.count_documents({})
        projects_count = await db.projects.count_documents({})
        documents_total = await db.documents.count_documents({})
        documents_completed = await db.documents.count_documents({"status": "completed"})
        documents_failed = await db.documents.count_documents({"status": "failed"})
        documents_processing = await db.documents.count_documents({"status": "processing"})
        documents_needs_review = await db.documents.count_documents({"status": "needs_review"})
        
        # QA statistics
        documents_qa_passed = await db.documents.count_documents({"qa_status": {"$in": ["passed", "approved_manual"]}})
        documents_qa_failed = await db.documents.count_documents({"qa_status": {"$in": ["failed", "rejected_manual"]}})
        documents_qa_pending = await db.documents.count_documents({"qa_status": {"$in": ["pending", "manual_review"]}})
        
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
        
        projects_count = await db.projects.count_documents({"company_id": current_user.company_id})
        documents_total = await db.documents.count_documents({
            "project_id": {"$in": [p["id"] for p in await db.projects.find({"company_id": current_user.company_id}).to_list(1000)]}
        })
        documents_completed = await db.documents.count_documents({
            "project_id": {"$in": [p["id"] for p in await db.projects.find({"company_id": current_user.company_id}).to_list(1000)]},
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
    
    # Check access permissions
    if current_user.role == "client" and current_user.company_id != project["company_id"]:
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
    return [User(**user) for user in users]

@api_router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(user_id: str, status_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Only staff can modify users")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": status_data["is_active"]}}
    )
    
    return {"message": "User status updated"}

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
            system_message="You are a helpful AI assistant that answers questions about document data. Provide clear, accurate answers based on the extracted document data provided."
        ).with_model("openai", "gpt-4o")
        
        # Prepare context from extracted data
        context = "Available document data:\n\n"
        sources = []
        
        for doc in documents:
            if doc.get("extracted_data"):
                context += f"Document: {doc['original_filename']}\n"
                context += f"Data: {json.dumps(doc['extracted_data'], indent=2)}\n\n"
                sources.append(doc['original_filename'])
        
        prompt = f"""
        Based on the following document data, answer this question: {question_data.question}
        
        {context}
        
        Please provide a clear, helpful answer based only on the data shown above. If the data doesn't contain information to answer the question, say so clearly.
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        return {
            "answer": response,
            "sources": sources[:5],  # Limit sources
            "documents_consulted": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error processing AI question: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing question")

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

async def generate_pdf_plan_with_ai(
    project: dict,
    company: dict,
    documents: List[dict],
    instruction: str
) -> PDFManagerPlan:
    """
    Generate a plan for PDF renaming and reordering using AI (GPT-4o).
    Returns a plan with rename operations, reorder sequence, and validation.
    """
    try:
        # Get AI configuration for document processing
        ai_config = await get_ai_config_for_task(project["id"], "document_processing")
        
        # Prepare documents metadata for LLM (lightweight)
        docs_metadata = []
        for doc in documents:
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
            
            docs_metadata.append(metadata)
        
        # Build LLM prompt
        system_prompt = """You are an expert document management AI planner. Your task is to analyze natural language instructions and generate a deterministic plan for renaming and reordering PDF documents.

RULES:
1. Return ONLY valid JSON, no markdown or explanations.
2. Use only the metadata provided - do not invent data.
3. For rename operations, use the document ID in "from_id" and generate a safe filename in "to_name".
4. Preserve file extensions (.pdf).
5. For reordering, ALWAYS provide "reorder_ids" array with ALL document IDs in the desired order.
6. If no specific order is mentioned, maintain current order in reorder_ids.
7. Detect conflicts: duplicate names, missing required metadata, ambiguous instructions.
8. Set confidence (0.0-1.0) based on instruction clarity and metadata availability.

OUTPUT FORMAT (MANDATORY):
{
  "rename_operations": [
    {"from_id": "doc_id", "from_name": "current.pdf", "to_name": "new_name.pdf"}
  ],
  "reorder_ids": ["doc_id_1", "doc_id_2", "doc_id_3"],
  "validation": {
    "confidence": 0.95,
    "conflicts": [],
    "warnings": []
  }
}

IMPORTANT: reorder_ids MUST contain ALL document IDs. If instruction doesn't mention ordering, use the same order as provided in DOCUMENTS METADATA."""

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
                to_name=op["to_name"]
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
        
        return PDFManagerPlan(
            rename_operations=rename_ops,
            reorder_ids=reorder_ids,
            validation=validation
        )
        
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

async def generate_pdf_page_plan_with_ai(
    project: dict,
    pdf_filename: str,
    pdf_path: str,
    instruction: str
) -> PDFPagePlan:
    """
    Generate a plan for reordering pages within a single PDF using AI.
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
        for page_num in range(total_pages):
            try:
                page = reader.pages[page_num]
                text = page.extract_text()
                # Truncate text to first 500 characters to keep prompt manageable
                text_preview = text[:500] if text else "[No text extracted]"
                pages_content.append({
                    "page_number": page_num + 1,
                    "text_preview": text_preview
                })
            except Exception as e:
                logger.warning(f"Error extracting text from page {page_num + 1}: {str(e)}")
                pages_content.append({
                    "page_number": page_num + 1,
                    "text_preview": "[Error extracting text]"
                })
        
        # Build LLM prompt
        system_prompt = """Eres un experto en gestión de páginas PDF con IA. Tu tarea es analizar el contenido de las páginas de un PDF y generar un plan para reordenarlas según instrucciones en lenguaje natural.

REGLAS:
1. Devuelve SOLO JSON válido, sin markdown ni explicaciones.
2. Los números de página empiezan en 1 (la primera página es 1, no 0).
3. Analiza el contenido de texto de cada página para tomar decisiones informadas.
4. Genera una secuencia completa que incluya TODAS las páginas.
5. Proporciona un razonamiento claro EN ESPAÑOL explicando qué páginas identificaste y por qué.
6. Establece la confianza (0.0-1.0) basándote en qué tan bien encontraste el contenido mencionado en las instrucciones.

FORMATO DE SALIDA (OBLIGATORIO):
{
  "new_page_sequence": [3, 1, 2, 4, 5],
  "confidence": 0.95,
  "reasoning": "Encontré 'notas importantes' en la página 3, la moví a la segunda posición como se solicitó. La página 1 permanece primero, la página 2 se movió a la tercera posición."
}

IMPORTANTE: new_page_sequence DEBE contener TODOS los números de página (1 a total_pages) exactamente una vez."""

        # Build pages content section
        pages_info = "\n\n".join([
            f"PÁGINA {page['page_number']}:\n{page['text_preview']}"
            for page in pages_content
        ])

        user_prompt = f"""ARCHIVO PDF: {pdf_filename}
TOTAL DE PÁGINAS: {total_pages}

CONTENIDO DE LAS PÁGINAS:
{pages_info}

INSTRUCCIÓN:
{instruction}

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


@api_router.post("/projects/{project_id}/pdf-page-manager/plan")
async def create_pdf_page_plan(
    project_id: str,
    plan_request: PDFPageManagerPlanRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate a plan for reordering pages within a specific PDF.
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
        # file_path is stored as absolute path, so use it directly
        pdf_path = Path(document["file_path"])
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail="PDF file not found on server"
            )
        
        logger.info(f"Generating PDF page plan for {plan_request.pdf_filename}")
        
        # Generate plan using AI
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
            plan=plan,
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
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found on server")
        
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
        
        logger.info(f"Executing PDF page reordering for job {job_id}")
        
        # Execute reordering
        output_path = await execute_pdf_page_reorder(job, str(pdf_path))
        
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
        
        logger.info(f"PDF page reordering completed successfully. Job ID: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "result_url": result_url,
            "result_filename": output_filename,
            "message": "Page reordering completed successfully"
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
    Download a reordered PDF file (authenticated).
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
        
        # Get file path
        output_dir = UPLOAD_DIR / "pdf_page_reorder_output"
        file_path = output_dir / file_name
        
        if not file_path.exists():
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

1. **Dashboard**: Vista general con estadísticas de empresas, proyectos, documentos procesados, QA aprobados/fallidos, etc.

2. **Empresas**: Gestión de empresas cliente. Puedes crear, editar y filtrar empresas por corporación y estado (Activa/Inactiva). Campos: nombre, email, teléfono, asesor comercial, segmento/industria, corporación, dirección.

3. **Proyectos**: Gestión de proyectos de digitalización por empresa. Cada proyecto tiene nombre, descripción, estado (activo/completado) e instrucciones semánticas para la IA.

4. **Documentos (dentro de Proyectos)**: Sube PDFs para procesamiento. El sistema realiza QA automático y extracción de datos con IA. Estados: subido, QA en proceso, QA aprobado/fallado, procesando, completado.

5. **PDF Manager IA**: Renombra y reordena PDFs de un proyecto usando lenguaje natural. Genera un plan, lo previsualizas, y lo ejecutas. Descarga ZIP con archivos renombrados y reordenados.

6. **PDF Manager IA por Página**: Reordena páginas DENTRO de un PDF específico. Seleccionas un PDF, das instrucciones ("mover página 3 al inicio"), la IA analiza el contenido y genera el nuevo PDF.

7. **Agentes QA**: Configura reglas de calidad para validar PDFs antes de procesarlos. Ejemplo: "verificar que tenga fecha", "debe contener palabra clave X".

8. **Hallazgos QA**: Visualiza documentos que fallaron QA y requieren revisión manual.

9. **Datos Extraídos**: Consulta toda la información extraída por IA de los PDFs procesados (fechas, montos, nombres, etc.).

10. **Segmentos**: Define segmentos de industria para clasificar empresas (Tecnología, Salud, Finanzas, etc.).

11. **Configuración IA**: Configura API keys de OpenAI por proyecto para los tres procesos: Extracción de datos, Agente QA, y Reordenamiento/Renombrado.

12. **Usuarios**: Gestión de usuarios del sistema. Roles: staff (administrador), asesor (asignado a empresas), cliente (acceso limitado a su empresa).

INSTRUCCIONES:
- Responde SIEMPRE en español
- Sé claro, conciso y útil
- Si no sabes algo, admítelo
- Proporciona ejemplos cuando sea posible
- Si la pregunta es ambigua, pide aclaración"""

        user_prompt = f"""Pregunta del usuario: {question}

Por favor, proporciona una respuesta clara y útil."""

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