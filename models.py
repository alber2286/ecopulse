from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(30), nullable=False)
    # roles: admin, supervisor, oficina_admin, oficina_cobro, cobrador
    activo = db.Column(db.Boolean, default=True)
    creado = db.Column(db.DateTime, default=datetime.utcnow)
    zonas_asignadas = db.Column(db.String(500), default='')

    def tiene_permiso(self, permiso):
        permisos = {
            'admin':         ['todo'],
            'supervisor':    ['ver_zona','carga_inicial','autorizar_cobrador'],
            'oficina_admin': ['editar_maquina','cambiar_estado','agregar_maquina','borrar_maquina_con_clave','ver_todo'],
            'oficina_cobro': ['confirmar_cobro','ver_reportes','exportar'],
            'cobrador':      ['cobro_basico'],
        }
        lista = permisos.get(self.rol, [])
        return 'todo' in lista or permiso in lista


class Maquina(db.Model):
    __tablename__ = 'maquinas'
    id = db.Column(db.Integer, primary_key=True)
    serie = db.Column(db.String(50), unique=True, nullable=False)
    modelo = db.Column(db.String(100), default='')
    zona = db.Column(db.String(100), default='')
    nombre_punto = db.Column(db.String(200), default='')
    # estados: ok, danada, reparando, necesita_retirar, caso_muni, robada, extraviada, necesita_cobro
    estado = db.Column(db.String(30), default='ok')
    led = db.Column(db.String(10), default='verde')  # verde, amarillo, rojo
    marcador_entrada = db.Column(db.Float, default=0)
    marcador_salida = db.Column(db.Float, default=0)
    activa = db.Column(db.Boolean, default=True)
    fecha_instalacion = db.Column(db.DateTime, default=datetime.utcnow)
    notas = db.Column(db.Text, default='')
    cobros = db.relationship('Cobro', backref='maquina', lazy=True)
    reparaciones = db.relationship('Reparacion', backref='maquina', lazy=True)
    historial_ubicaciones = db.relationship('HistorialUbicacion', backref='maquina', lazy=True)
    contratos = db.relationship('Contrato', backref='maquina', lazy=True)

    def led_color(self):
        ROJO  = ['danada','necesita_retirar','caso_muni','robada','extraviada']
        AMARILLO = ['reparando','necesita_cobro']
        if self.estado in ROJO: return 'rojo'
        if self.estado in AMARILLO: return 'amarillo'
        return 'verde'

    def estado_label(self):
        labels = {
            'ok':'OK','danada':'Dañada','reparando':'Reparando en progreso',
            'necesita_retirar':'Necesita retirar','caso_muni':'Caso Muni',
            'robada':'Robada','extraviada':'Extraviada','necesita_cobro':'Necesita cobro'
        }
        return labels.get(self.estado, self.estado)


class Cobro(db.Model):
    __tablename__ = 'cobros'
    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    serie = db.Column(db.String(50))
    zona = db.Column(db.String(100))
    nombre_punto = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    semana = db.Column(db.String(20))
    cobrador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    cobrador_nombre = db.Column(db.String(100))
    marcador_entrada_anterior = db.Column(db.Float, default=0)  # A
    marcador_entrada_actual = db.Column(db.Float, default=0)    # B
    marcador_salida_anterior = db.Column(db.Float, default=0)   # C
    marcador_salida_actual = db.Column(db.Float, default=0)     # D
    resultado_entrada = db.Column(db.Float, default=0)          # E = B-A
    resultado_salida = db.Column(db.Float, default=0)           # F = D-C
    neto = db.Column(db.Float, default=0)                       # G = E-F
    nota = db.Column(db.Text, default='')
    confirmado = db.Column(db.Boolean, default=False)
    confirmado_por = db.Column(db.String(100))
    editado_por = db.Column(db.String(100))
    fecha_edicion = db.Column(db.DateTime)


class Reparacion(db.Model):
    __tablename__ = 'reparaciones'
    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    serie = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tecnico = db.Column(db.String(100))
    tipo = db.Column(db.String(50))  # taller_eco, en_punto
    piezas = db.Column(db.Text, default='')  # JSON list
    nota = db.Column(db.Text, default='')
    costo = db.Column(db.Float, default=0)
    registrado_por = db.Column(db.String(100))


class HistorialUbicacion(db.Model):
    __tablename__ = 'historial_ubicaciones'
    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    serie = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    zona_anterior = db.Column(db.String(100))
    punto_anterior = db.Column(db.String(200))
    zona_nueva = db.Column(db.String(100))
    punto_nuevo = db.Column(db.String(200))
    motivo = db.Column(db.String(200))
    registrado_por = db.Column(db.String(100))


class Contrato(db.Model):
    __tablename__ = 'contratos'
    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    serie = db.Column(db.String(50))
    nombre_negocio = db.Column(db.String(200))
    nombre_encargado = db.Column(db.String(200))
    cedula = db.Column(db.String(30))
    telefono = db.Column(db.String(30))
    zona = db.Column(db.String(100))
    nombre_punto = db.Column(db.String(200))
    porcentaje_ganancia = db.Column(db.Float, default=0)
    foto_contrato = db.Column(db.String(300))  # ruta archivo
    ubicacion_gps = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    registrado_por = db.Column(db.String(100))


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(30))
    accion = db.Column(db.String(200))
    detalle = db.Column(db.Text)
    ip = db.Column(db.String(50))
