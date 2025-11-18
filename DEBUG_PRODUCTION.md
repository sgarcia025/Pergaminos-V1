# DEBUG PARA PRODUCCIÓN - Error al cargar empresas/usuarios

## Verificar que los cambios se desplegaron correctamente

### 1. Verificar el modelo User en producción
Conéctate al servidor de producción y ejecuta:
```bash
grep -A 8 "class User(BaseModel):" /ruta/backend/server.py
```

Debes ver:
```python
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str  # "staff", "asesor", or "client"
    company_id: Optional[str] = Field(default=None)
    company_ids: List[str] = Field(default_factory=list)
    assigned_corporation: Optional[str] = Field(default=None)
```

### 2. Verificar la función get_current_user
```bash
grep -A 20 "async def get_current_user" /ruta/backend/server.py | head -25
```

Debe incluir estas líneas:
```python
# Ensure backward compatibility with users missing new fields
if 'company_ids' not in user:
    user['company_ids'] = []
if 'assigned_corporation' not in user:
    user['assigned_corporation'] = None

return User(**user)
```

### 3. Verificar logs de producción en tiempo real
```bash
tail -f /var/log/tu_app/backend.log
```

Luego intenta cargar empresas y mira qué error aparece EXACTAMENTE.

### 4. Reiniciar el backend en producción
```bash
# Dependiendo de tu setup:
sudo systemctl restart tu-backend
# o
sudo supervisorctl restart backend
# o
pm2 restart backend
```

### 5. Si el error persiste, necesito ver:

**A. Logs exactos del error:**
```bash
tail -n 100 /var/log/tu_app/backend.log | grep -i "error\|exception" -A 5
```

**B. Versión de Pydantic en producción:**
```bash
pip show pydantic
```

**C. Verificar que MongoDB tenga usuarios:**
```bash
mongo tu_database --eval "db.users.findOne()"
```

## Solución alternativa temporal

Si nada funciona, como solución temporal puedes hacer que TODOS los campos sean opcionales:

```python
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str
    company_id: Optional[str] = None
    company_ids: Optional[List[str]] = None  # Hacer opcional
    assigned_corporation: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

Y en get_current_user:
```python
user_obj = User(**user)
if user_obj.company_ids is None:
    user_obj.company_ids = []
return user_obj
```

## IMPORTANTE: 
El código en este entorno (e1) YA ESTÁ CORRECTO. El problema es que en producción:
1. Los cambios no se desplegaron correctamente, O
2. No se reinició el servidor, O  
3. Hay un problema de caché, O
4. Hay alguna diferencia en las versiones de librerías
