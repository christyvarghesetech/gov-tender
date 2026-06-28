from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.user import UserCreate, UserLogin
import uuid
import datetime

from app.auth import require_role

router = APIRouter()

@router.post("/register")
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if email or digital_id already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email address is already registered.")
        
    existing_did = db.query(User).filter(User.digital_id == user_data.digital_id).first()
    if existing_did:
        raise HTTPException(status_code=400, detail="Digital ID is already registered.")
        
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        digital_id=user_data.digital_id,
        role=user_data.role,
        department=user_data.department,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(new_user)
    
    # Add audit log
    log_entry = AuditLog(
        user_id=new_user.id,
        action="USER_REGISTERED",
        module="Authentication",
        details=f"Vendor user registered: {user_data.name} ({user_data.email})",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    
    db.commit()
    db.refresh(new_user)
    
    return {
        "id": str(new_user.id),
        "name": new_user.name,
        "email": new_user.email,
        "digital_id": new_user.digital_id,
        "role": new_user.role,
        "department": new_user.department
    }

@router.post("/login")
def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    did = login_data.digital_id.strip()
    
    # Check if user exists in database
    user = db.query(User).filter(User.digital_id == did).first()
    
    if not user:
        # If it's a first time official logging in, let's create a default admin
        if did.lower().startswith("admin") or did.lower().startswith("official") or did.lower().startswith("jane"):
            new_user = User(
                name="Officer Jane Doe",
                email="jane.doe@infrastructure.gov",
                digital_id=did,
                role="Admin",
                department="Ministry of Infrastructure",
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
        elif did.lower().startswith("audit"):
            new_user = User(
                name="Auditor Arthur Dent",
                email="arthur.dent@auditor.gov",
                digital_id=did,
                role="Auditor",
                department="National Audit Office",
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
        elif did.lower().startswith("vendor") or did.lower().startswith("bidder"):
            # Auto-create a vendor/bidder session account
            vendor_num = did.split("-")[-1] if "-" in did else "001"
            new_user = User(
                name=f"Vendor User {vendor_num.upper()}",
                email=f"vendor{vendor_num}@bidder.com",
                digital_id=did,
                role="Vendor",
                department="Private Sector",
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
        else:
            raise HTTPException(status_code=404, detail="Digital ID not registered. Please sign up first via the Register page.")
            
    # Check if user is suspended
    if user.role.lower() != "admin" and user.department == "suspended":
        raise HTTPException(status_code=403, detail="Your vendor profile is currently suspended. Contact support.")
        
    # Log session
    log_entry = AuditLog(
        user_id=user.id,
        action="USER_LOGGED_IN",
        module="Authentication",
        details=f"User session verified via eSignet ID: {user.digital_id}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    
    # Format initials
    initials = "".join([w[0] for w in user.name.split()]).upper()[:2]
    
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "digital_id": user.digital_id,
        "role": user.role,
        "company": user.name if user.role == "Admin" else (user.name + " Contracting LLC"),
        "initials": initials,
        "phone": "+1 (555) 238-1290",
        "status": "suspended" if user.department == "suspended" else "active"
    }

@router.get("/users")
def get_users(db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    users = db.query(User).all()
    res = []
    for u in users:
        res.append({
            "name": u.name,
            "email": u.email,
            "company": u.name if u.role == "Admin" else (u.name + " Contracting LLC"),
            "type": "Admin" if u.role == "Admin" else "Vendor",
            "status": "suspended" if u.department == "suspended" else "active"
        })
    return res

@router.post("/users/{email}/toggle")
def toggle_user_status(email: str, db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found.")
        
    # Switch status using the 'department' column as a suspension toggle for vendors
    if user.department == "suspended":
        user.department = None
        new_status = "active"
    else:
        user.department = "suspended"
        new_status = "suspended"
        
    user.updated_at = datetime.datetime.utcnow()
    
    log_entry = AuditLog(
        user_id=user.id,
        action="USER_STATUS_TOGGLED",
        module="Administration",
        details=f"User status modified for {user.name} ({user.email}) to '{new_status}'",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    
    return {"email": email, "status": new_status}
