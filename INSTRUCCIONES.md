# EcoPulse — MAGO Solutions
## Guía de instalación y arranque

### REQUISITOS
- Python 3.10 o superior (ya lo tenés instalado)
- pip

---

### PASO 1 — Crear carpeta del proyecto
Copiá los archivos en una carpeta, por ejemplo:
```
C:\Users\TuUsuario\ecopulse\
```

Los archivos que necesitás:
```
ecopulse/
├── app.py
├── models.py
├── requirements.txt
├── templates/        (carpeta vacía por ahora)
├── static/           (carpeta vacía por ahora)
└── uploads/
    └── contratos/    (carpeta vacía)
```

---

### PASO 2 — Instalar dependencias
Abrí terminal o CMD en la carpeta del proyecto:
```bash
pip install -r requirements.txt
```

---

### PASO 3 — Arrancar el sistema
```bash
python app.py
```

Verás esto en pantalla:
```
✅ Admin creado: admin@ecopulse.com / admin123
🚀 EcoPulse by MAGO Solutions arrancando...
 * Running on http://127.0.0.1:5000
```

---

### PASO 4 — Abrir en el navegador
Ve a: http://localhost:5000

**Usuario inicial:**
- Email: admin@ecopulse.com
- Password: admin123

⚠️ Cambiá la contraseña del admin inmediatamente después del primer login.

---

### USUARIOS Y ROLES
| Rol | Acceso |
|-----|--------|
| admin | Todo el sistema |
| supervisor | Carga inicial, autoriza cobradores, su zona |
| oficina_admin | Edita máquinas, estados, marcadores, contratos |
| oficina_cobro | Confirma cobros, reportes, exportación |
| cobrador | Solo ingresa B y D de sus máquinas asignadas |

---

### ESTADOS DE MÁQUINA Y LED
| Estado | LED | Color |
|--------|-----|-------|
| ok | Verde | Todo bien |
| necesita_cobro | Amarillo | Pendiente de cobro |
| reparando | Amarillo | En reparación |
| danada | Rojo | Dañada |
| necesita_retirar | Rojo | Retirar del punto |
| caso_muni | Rojo | Problema municipal |
| robada | Rojo | Robada |
| extraviada | Rojo | Extraviada |

---

### LÓGICA DE COBRO
```
A = Marcador entrada semana anterior (sistema lo trae)
B = Marcador entrada actual (cobrador ingresa)
C = Marcador salida semana anterior (sistema lo trae)
D = Marcador salida actual (cobrador ingresa)

E = B - A  (dinero que entró)
F = D - C  (dinero que salió)
G = E - F  (neto — lo que debe haber en la máquina)
```

---

### PRÓXIMOS PASOS CON CLAUDE
1. Templates HTML (login, dashboard, cobros, máquinas)
2. Integración Google Maps con capas
3. Exportación a Excel
4. PWA (instalable en celular)
5. Deploy en Railway.app

---

### ESTRUCTURA DE BASE DE DATOS
- **usuarios** — todos los usuarios del sistema
- **maquinas** — inventario completo de máquinas
- **cobros** — historial de lecturas semanales
- **reparaciones** — historial de reparaciones por pieza
- **historial_ubicaciones** — dónde ha estado cada máquina
- **contratos** — datos del cliente y contrato por punto
- **audit_log** — registro de todo lo que hace cada usuario

---

EcoPulse v1.0 | MAGO Solutions | 2026
