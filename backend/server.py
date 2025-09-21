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
    role: str  # "staff" or "client"

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str  # "staff" or "client"
    company_id: Optional[str] = None  # Only for client users
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str  # "staff" or "client"
    company_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Company(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # staff user id

class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by: str  # user id

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: User

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
    else:
        # Staff can see all companies
        companies = await db.companies.find().to_list(1000)
    
    return [Company(**company) for company in companies]

@api_router.get("/companies/{company_id}", response_model=Company)
async def get_company(company_id: str, current_user: User = Depends(get_current_user)):
    if current_user.role == "client" and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return Company(**company)

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
    
    documents = await db.documents.find({"project_id": project_id}).to_list(1000)
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

# Initialize default admin user
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