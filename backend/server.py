from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
    estado: Optional[str] = None  # Estado de la empresa (texto libre)
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
    estado: Optional[str] = None
    corporacion: Optional[str] = None

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
    status: str = "uploaded"  # uploaded, processing, completed, failed, needs_review
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
    
    # Start AI processing in background
    import asyncio
    asyncio.create_task(process_document_with_ai(document.id, project))
    
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
        
        # Create semaphore to limit concurrent processing to 10
        semaphore = asyncio.Semaphore(10)
        
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

# AI Document Processing
async def process_document_with_ai(document_id: str, project: dict):
    """Process document with AI and extract data based on semantic instructions"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
        from dotenv import load_dotenv
        load_dotenv()
        
        # Update document status to processing
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"status": "processing"}}
        )
        
        # Get document details
        document = await db.documents.find_one({"id": document_id})
        if not document:
            return
        
        # Initialize AI chat with GPT-4o
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            await db.documents.update_one(
                {"id": document_id},
                {"$set": {"status": "failed"}}
            )
            return
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"doc_processing_{document_id}",
            system_message="You are an expert document analysis AI. Extract structured data from documents based on specific instructions."
        ).with_model("openai", "gpt-4o")
        
        # Create file content for AI processing
        file_content = FileContentWithMimeType(
            file_path=document["file_path"],
            mime_type="application/pdf"
        )
        
        # Create processing prompt
        semantic_instructions = project.get("semantic_instructions", "")
        if not semantic_instructions:
            semantic_instructions = "Extract all key information, dates, names, amounts, and important details from this document."
        
        prompt = f"""
        Analyze this PDF document and extract structured data based on these instructions:
        
        {semantic_instructions}
        
        Please provide the extracted data in JSON format with clear field names and values.
        If certain information is not available, mark it as null.
        Focus on accuracy and completeness.
        """
        
        # Note: Switch to Gemini for file processing since it supports file attachments
        gemini_chat = LlmChat(
            api_key=api_key,
            session_id=f"doc_processing_gemini_{document_id}",
            system_message="You are an expert document analysis AI. Extract structured data from documents based on specific instructions."
        ).with_model("gemini", "gemini-2.0-flash")
        
        user_message = UserMessage(
            text=prompt,
            file_contents=[file_content]
        )
        
        # Process with AI
        response = await gemini_chat.send_message(user_message)
        
        # Try to parse JSON from response
        import json
        import re
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        extracted_data = {}
        
        if json_match:
            try:
                extracted_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                # If JSON parsing fails, store raw response
                extracted_data = {"raw_response": response, "status": "needs_review"}
        else:
            extracted_data = {"raw_response": response, "status": "needs_review"}
        
        # Update document with extracted data
        await db.documents.update_one(
            {"id": document_id},
            {
                "$set": {
                    "status": "completed",
                    "extracted_data": extracted_data,
                    "processed_at": datetime.now(timezone.utc)
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
        
        return {
            "companies_count": companies_count,
            "projects_count": projects_count,
            "documents_total": documents_total,
            "documents_completed": documents_completed,
            "documents_failed": documents_failed,
            "documents_processing": documents_processing,
            "documents_needs_review": documents_needs_review
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
@api_router.put("/documents/{document_id}/rename", response_model=Document)
async def rename_document(
    document_id: str,
    new_name: str = Form(...),
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
        {"$set": {"original_filename": new_name}}
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
    quality_checks: Dict[str, bool] = {
        "image_clarity": False,
        "document_orientation": False,
        "signature_detection": False,
        "seal_detection": False,
        "text_readability": False,
        "completeness_check": False
    }
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # user id

class QAAgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    qa_instructions: str
    project_ids: List[str] = []
    is_universal: bool = False
    quality_checks: Dict[str, bool]

class DocumentProcessRequest(BaseModel):
    semantic_instructions: str

class AIQuestionRequest(BaseModel):
    question: str
    include_context: bool = True

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