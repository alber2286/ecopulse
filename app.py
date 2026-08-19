from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, Usuario, Maquina, Cobro, Reparacion, HistorialUbicacion, Contrato, AuditLog, MovimientoBodega
from datetime import datetime
import os, json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ecopulse-mago-solutions-2026')
import os as _os
_db_url = _os.environ.get('DATABASE_URL', 'sqlite:///ecopulse.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/contratos'

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

def audit(accion, detalle=''):
    try:
        log = AuditLog(
            usuario=current_user.nombre if current_user.is_authenticated else 'sistema',
            rol=current_user.rol if current_user.is_authenticated else '-',
            accion=accion, detalle=detalle,
            ip=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except:
        pass

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = Usuario.query.filter_by(email=email, activo=True).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            audit('LOGIN', 'Ingreso al sistema')
            return redirect(url_for('dashboard'))
        flash('Email o contrasena incorrectos', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    audit('LOGOUT')
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.rol == 'cobrador':
        return redirect(url_for('cobrador'))
    maquinas = Maquina.query.filter_by(activa=True).all()
    verdes = sum(1 for m in maquinas if m.led_color() == 'verde')
    amarillas = sum(1 for m in maquinas if m.led_color() == 'amarillo')
    rojas = sum(1 for m in maquinas if m.led_color() == 'rojo')
    cobros_recientes = Cobro.query.order_by(Cobro.fecha.desc()).limit(10).all()
    zonas = {}
    for c in Cobro.query.all():
        if c.zona not in zonas:
            zonas[c.zona] = {'neto': 0, 'cnt': 0}
        zonas[c.zona]['neto'] += c.neto
        zonas[c.zona]['cnt'] += 1
    return render_template('dashboard.html',
        total=len(maquinas), verdes=verdes, amarillas=amarillas, rojas=rojas,
        cobros=cobros_recientes, zonas=zonas,
        maquinas_alerta=[m for m in maquinas if m.led_color() != 'verde']
    )
@app.route('/maquinas')
@login_required
def maquinas():
    todas = Maquina.query.filter_by(activa=True).order_by(Maquina.serie).all()
    return render_template('maquinas.html', maquinas=todas)

@app.route('/maquinas/nueva', methods=['POST'])
@login_required
def nueva_maquina():
    if not (current_user.tiene_permiso('agregar_maquina') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    data = request.json
    if Maquina.query.filter_by(serie=data['serie']).first():
        return jsonify({'error': 'Serie ya existe'}), 400
    m = Maquina(
        serie=data['serie'], modelo=data.get('modelo', ''),
        zona=data.get('zona', ''), nombre_punto=data.get('nombre_punto', ''),
        estado='ok', led='verde',
        marcador_entrada=float(data.get('marcador_entrada', 0)),
        marcador_salida=float(data.get('marcador_salida', 0)),
        notas=data.get('notas', ''),
        url_ubicacion=data.get('url_ubicacion', ''),
        latitud=data.get('latitud'),
        longitud=data.get('longitud')
    )
    db.session.add(m)
    db.session.flush()
    if data.get('zona'):
        h = HistorialUbicacion(
            maquina_id=m.id, serie=m.serie,
            zona_nueva=m.zona, punto_nuevo=m.nombre_punto,
            motivo='Instalacion inicial',
            registrado_por=current_user.nombre
        )
        db.session.add(h)
    db.session.commit()
    audit('NUEVA_MAQUINA', f'Serie: {m.serie} Punto: {m.nombre_punto}')
    return jsonify({'ok': True, 'id': m.id})

@app.route('/maquinas/<int:mid>/estado', methods=['POST'])
@login_required
def cambiar_estado(mid):
    if not (current_user.tiene_permiso('cambiar_estado') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    m = Maquina.query.get_or_404(mid)
    data = request.json
    estado_anterior = m.estado
    m.estado = data['estado']
    m.led = m.led_color()
    db.session.commit()
    audit('CAMBIO_ESTADO', f'{m.serie}: {estado_anterior} -> {m.estado}')
    return jsonify({'ok': True, 'led': m.led})

@app.route('/maquinas/<int:mid>/editar', methods=['POST'])
@login_required
def editar_maquina(mid):
    if not (current_user.tiene_permiso('editar_maquina') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    m = Maquina.query.get_or_404(mid)
    data = request.json
    zona_cambio = data.get('zona') and data['zona'] != m.zona
    punto_cambio = data.get('nombre_punto') and data['nombre_punto'] != m.nombre_punto
    if zona_cambio or punto_cambio:
        h = HistorialUbicacion(
            maquina_id=m.id, serie=m.serie,
            zona_anterior=m.zona, punto_anterior=m.nombre_punto,
            zona_nueva=data.get('zona', m.zona),
            punto_nuevo=data.get('nombre_punto', m.nombre_punto),
            motivo=data.get('motivo_cambio', 'Actualizacion'),
            registrado_por=current_user.nombre
        )
        db.session.add(h)
    if data.get('serie'): m.serie = data['serie']
    if data.get('modelo'): m.modelo = data['modelo']
    if data.get('zona'): m.zona = data['zona']
    if data.get('nombre_punto'): m.nombre_punto = data['nombre_punto']
    if data.get('marcador_entrada') is not None:
        m.marcador_entrada = float(data['marcador_entrada'])
    if data.get('marcador_salida') is not None:
        m.marcador_salida = float(data['marcador_salida'])
    if data.get('notas'): m.notas = data['notas']
    db.session.commit()
    audit('EDITAR_MAQUINA', f'Serie: {m.serie}')
    return jsonify({'ok': True})

@app.route('/maquinas/<int:mid>/borrar', methods=['POST'])
@login_required
def borrar_maquina(mid):
    if not (current_user.tiene_permiso('borrar_maquina_con_clave') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    data = request.json
    admin = Usuario.query.filter_by(rol='admin', activo=True).first()
    if not admin or not bcrypt.check_password_hash(admin.password, data.get('clave_admin', '')):
        return jsonify({'error': 'Clave admin incorrecta'}), 403
    m = Maquina.query.get_or_404(mid)
    m.activa = False
    db.session.commit()
    audit('BORRAR_MAQUINA', f'Serie: {m.serie} - Razon: {data.get("razon", "")}')
    return jsonify({'ok': True})

@app.route('/maquinas/<int:mid>/historial')
@login_required
def historial_maquina(mid):
    m = Maquina.query.get_or_404(mid)
    cobros = Cobro.query.filter_by(maquina_id=mid).order_by(Cobro.fecha.desc()).all()
    reps = Reparacion.query.filter_by(maquina_id=mid).order_by(Reparacion.fecha.desc()).all()
    ubicaciones = HistorialUbicacion.query.filter_by(maquina_id=mid).order_by(HistorialUbicacion.fecha.desc()).all()
    return render_template('historial_maquina.html', m=m, cobros=cobros, reps=reps, ubicaciones=ubicaciones)

@app.route('/cobros')
@login_required
def cobros():
    if current_user.rol == 'cobrador':
        lista = Cobro.query.filter_by(cobrador_id=current_user.id).order_by(Cobro.fecha.desc()).limit(50).all()
    else:
        lista = Cobro.query.order_by(Cobro.fecha.desc()).limit(100).all()
    maquinas_activas = Maquina.query.filter_by(activa=True, estado='ok').order_by(Maquina.serie).all()
    return render_template('cobros.html', cobros=lista, maquinas=maquinas_activas)

@app.route('/cobros/nuevo', methods=['POST'])
@login_required
def nuevo_cobro():
    data = request.json
    m = Maquina.query.filter_by(serie=data['serie'], activa=True).first()
    if not m:
        return jsonify({'error': 'Maquina no encontrada'}), 404
    A = m.marcador_entrada
    C = m.marcador_salida
    B = float(data['marcador_entrada_actual'])
    D = float(data['marcador_salida_actual'])
    E = B - A
    F = D - C
    G = E - F
    cobro = Cobro(
        maquina_id=m.id, serie=m.serie,
        zona=m.zona, nombre_punto=m.nombre_punto,
        semana=data.get('semana', ''),
        cobrador_id=current_user.id,
        cobrador_nombre=current_user.nombre,
        marcador_entrada_anterior=A, marcador_entrada_actual=B,
        marcador_salida_anterior=C, marcador_salida_actual=D,
        resultado_entrada=E, resultado_salida=F, neto=G,
        nota=data.get('nota', '')
    )
    m.marcador_entrada = B
    m.marcador_salida = D
    if m.estado == 'necesita_cobro':
        m.estado = 'ok'
        m.led = 'verde'
    db.session.add(cobro)
    db.session.commit()
    audit('NUEVO_COBRO', f'{m.serie} | E:{E} F:{F} G:{G}')
    return jsonify({'ok': True, 'neto': G, 'e': E, 'f': F})

@app.route('/cobros/<int:cid>/confirmar', methods=['POST'])
@login_required
def confirmar_cobro(cid):
    if not (current_user.tiene_permiso('confirmar_cobro') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    c = Cobro.query.get_or_404(cid)
    c.confirmado = True
    c.confirmado_por = current_user.nombre
    db.session.commit()
    audit('CONFIRMAR_COBRO', f'Cobro ID:{cid} Serie:{c.serie}')
    return jsonify({'ok': True})

@app.route('/cobros/<int:cid>/editar', methods=['POST'])
@login_required
def editar_cobro(cid):
    if not (current_user.tiene_permiso('editar_maquina') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    c = Cobro.query.get_or_404(cid)
    data = request.json
    if data.get('marcador_entrada_actual') is not None:
        B = float(data['marcador_entrada_actual'])
        D = float(data.get('marcador_salida_actual', c.marcador_salida_actual))
        c.marcador_entrada_actual = B
        c.marcador_salida_actual = D
        c.resultado_entrada = B - c.marcador_entrada_anterior
        c.resultado_salida = D - c.marcador_salida_anterior
        c.neto = c.resultado_entrada - c.resultado_salida
    if data.get('nota'):
        c.nota = data['nota']
    c.editado_por = current_user.nombre
    c.fecha_edicion = datetime.utcnow()
    db.session.commit()
    audit('EDITAR_COBRO', f'Cobro ID:{cid}')
    return jsonify({'ok': True, 'neto': c.neto})

@app.route('/reparaciones')
@login_required
def reparaciones():
    lista = Reparacion.query.order_by(Reparacion.fecha.desc()).all()
    maquinas_all = Maquina.query.filter_by(activa=True).order_by(Maquina.serie).all()
    return render_template('reparaciones.html', reparaciones=lista, maquinas=maquinas_all)

@app.route('/reparaciones/nueva', methods=['POST'])
@login_required
def nueva_reparacion():
    data = request.json
    m = Maquina.query.filter_by(serie=data['serie'], activa=True).first()
    if not m:
        return jsonify({'error': 'Maquina no encontrada'}), 404
    rep = Reparacion(
        maquina_id=m.id, serie=m.serie,
        tecnico=data.get('tecnico', ''),
        tipo=data.get('tipo', ''),
        piezas=json.dumps(data.get('piezas', [])),
        nota=data.get('nota', ''),
        costo=float(data.get('costo', 0)),
        registrado_por=current_user.nombre
    )
    db.session.add(rep)
    db.session.commit()
    audit('NUEVA_REPARACION', f'{m.serie} | Piezas: {data.get("piezas", [])}')
    return jsonify({'ok': True})

@app.route('/mapa')
@login_required
def mapa():
    import json as json_lib
    maquinas = Maquina.query.filter_by(activa=True).all()
    maquinas_json = []
    for m in maquinas:
        ultimo_cobro = Cobro.query.filter_by(maquina_id=m.id).order_by(Cobro.fecha.desc()).first()
        maquinas_json.append({
            'id': m.id,
            'serie': m.serie,
            'zona': m.zona,
            'nombre_punto': m.nombre_punto,
            'estado': m.estado,
            'lat': m.latitud,
            'lng': m.longitud,
            'url_ubicacion': m.url_ubicacion or '',
            'ultimo_neto': ultimo_cobro.neto if ultimo_cobro else None,
            'marcador_entrada': m.marcador_entrada,
            'marcador_salida': m.marcador_salida
        })
    return render_template('mapa.html', maquinas=maquinas, maquinas_json=json_lib.dumps(maquinas_json))

@app.route('/exportar')
@login_required
def exportar_page():
    return render_template('exportar.html')

@app.route('/exportar/data')
@login_required
def exportar_data():
    if not (current_user.tiene_permiso('exportar') or current_user.tiene_permiso('todo')):
        return jsonify({'error': 'Sin permiso'}), 403
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    zona = request.args.get('zona', '')
    query = Cobro.query
    if desde:
        query = query.filter(Cobro.fecha >= datetime.strptime(desde, '%Y-%m-%d'))
    if hasta:
        query = query.filter(Cobro.fecha <= datetime.strptime(hasta, '%Y-%m-%d'))
    if zona:
        query = query.filter(Cobro.zona == zona)
    cobros = query.order_by(Cobro.fecha.desc()).all()
    data = [{
        'serie': c.serie, 'zona': c.zona, 'punto': c.nombre_punto,
        'fecha': c.fecha.strftime('%Y-%m-%d'), 'semana': c.semana,
        'cobrador': c.cobrador_nombre,
        'A': c.marcador_entrada_anterior, 'B': c.marcador_entrada_actual,
        'C': c.marcador_salida_anterior, 'D': c.marcador_salida_actual,
        'E': c.resultado_entrada, 'F': c.resultado_salida, 'G': c.neto,
        'nota': c.nota, 'confirmado': c.confirmado
    } for c in cobros]
    return jsonify({'ok': True, 'registros': len(data), 'data': data})

@app.route('/usuarios')
@login_required
def usuarios():
    if not current_user.tiene_permiso('todo'):
        return redirect(url_for('dashboard'))
    lista = Usuario.query.all()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/usuarios/nuevo', methods=['POST'])
@login_required
def nuevo_usuario():
    if not current_user.tiene_permiso('todo'):
        return jsonify({'error': 'Sin permiso'}), 403
    data = request.json
    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email ya existe'}), 400
    u = Usuario(
        nombre=data['nombre'], email=data['email'],
        password=bcrypt.generate_password_hash(data['password']).decode('utf-8'),
        rol=data['rol'], zonas_asignadas=data.get('zonas', '')
    )
    db.session.add(u)
    db.session.commit()
    audit('NUEVO_USUARIO', f'{u.nombre} | Rol: {u.rol}')
    return jsonify({'ok': True})

@app.route('/audit')
@login_required
def audit_log():
    if not current_user.tiene_permiso('todo'):
        return redirect(url_for('dashboard'))
    logs = AuditLog.query.order_by(AuditLog.fecha.desc()).limit(200).all()
    return render_template('audit.html', logs=logs)

@app.route('/api/maquina/<serie>')
@login_required
def api_maquina(serie):
    m = Maquina.query.filter_by(serie=serie, activa=True).first()
    if not m:
        return jsonify({'error': 'No encontrada'}), 404
    return jsonify({
        'serie': m.serie, 'zona': m.zona, 'punto': m.nombre_punto,
        'estado': m.estado, 'led': m.led_color(),
        'marcador_entrada': m.marcador_entrada,
        'marcador_salida': m.marcador_salida
    })

def init_db():
    with app.app_context():
        db.create_all()
        if not Usuario.query.filter_by(rol='admin').first():
            admin = Usuario(
                nombre='Administrador',
                email='admin@ecopulse.com',
                password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                rol='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print('Admin creado: admin@ecopulse.com / admin123')



@app.route('/cobrador')
@login_required
def cobrador():
    if current_user.rol == 'cobrador':
        maquinas = Maquina.query.filter_by(activa=True, estado='ok').order_by(Maquina.serie).all()
    else:
        maquinas = Maquina.query.filter_by(activa=True).order_by(Maquina.serie).all()
    return render_template('cobrador.html', maquinas=maquinas)


@app.route('/api/leer-marcador', methods=['POST'])
@login_required
def leer_marcador():
    try:
        import anthropic
        import json as json_lib
        data = request.json
        imagen_base64 = data.get('imagen')
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            return jsonify({'entrada': None, 'salida': None, 'error': 'Sin API key'})
        client = anthropic.Anthropic(api_key=api_key)
        prompt_text = 'Analiza esta imagen de contadores de maquina slot. Lee los numeros. Si hay dos contadores: izquierdo es entrada, derecho es salida. Responde SOLO con JSON valido sin texto adicional, formato: {"entrada": NUMERO, "salida": NUMERO}. Si no puedes leer alguno usa null.'
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=100,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/jpeg',
                            'data': imagen_base64
                        }
                    },
                    {
                        'type': 'text',
                        'text': prompt_text
                    }
                ]
            }]
        )
        text = message.content[0].text.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        result = json_lib.loads(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'entrada': None, 'salida': None, 'error': str(e)})


with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(rol='admin').first():
        admin = Usuario(
            nombre='Administrador',
            email='admin@ecopulse.com',
            password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
            rol='admin'
        )
        db.session.add(admin)
        db.session.commit()
@app.route('/bodega')
@login_required
def bodega():
    if current_user.rol not in ['bodega', 'admin']:
        return redirect(url_for('dashboard'))
    movimientos = MovimientoBodega.query.order_by(MovimientoBodega.fecha.desc()).limit(50).all()
    maquinas = Maquina.query.filter_by(activa=True).order_by(Maquina.serie).all()
    cobradores = Usuario.query.filter_by(rol='cobrador', activo=True).all()
    return render_template('bodega.html', movimientos=movimientos, maquinas=maquinas, cobradores=cobradores)

@app.route('/bodega/movimiento', methods=['POST'])
@login_required
def bodega_movimiento():
    if current_user.rol not in ['bodega', 'admin']:
        return jsonify({'error': 'Sin permiso'}), 403
    data = request.json
    tipo = data.get('tipo')  # 'ingreso' o 'salida'
    serie = data.get('serie', '').strip().upper()
    m = Maquina.query.filter_by(serie=serie, activa=True).first()
    if not m:
        return jsonify({'error': f'Máquina {serie} no encontrada'}), 404

    mov = MovimientoBodega(
        maquina_id=m.id,
        serie=m.serie,
        tipo=tipo,
        quien_entrega=data.get('quien_entrega', ''),
        quien_recibe=data.get('quien_recibe', ''),
        motivo=data.get('motivo', ''),
        notas=data.get('notas', ''),
        registrado_por=current_user.nombre
    )

    if tipo == 'ingreso':
        m.estado = 'en_bodega'
        m.led = 'amarillo'
        m.cobrador_asignado_id = None
    elif tipo == 'salida':
        asignado_id = data.get('asignado_a_id')
        if asignado_id:
            cobrador = Usuario.query.get(asignado_id)
            if cobrador:
                m.cobrador_asignado_id = cobrador.id
                mov.asignado_a_id = cobrador.id
                mov.asignado_a_nombre = cobrador.nombre
        m.estado = 'ok'
        m.led = 'verde'

    db.session.add(mov)
    db.session.commit()
    audit(f'BODEGA_{tipo.upper()}', f'Serie: {serie} | Entrega: {data.get("quien_entrega")} | Recibe: {data.get("quien_recibe")}')
    return jsonify({'ok': True, 'serie': serie, 'tipo': tipo})

@app.route('/api/buscar-maquina/<serie>')
@login_required
def buscar_maquina(serie):
    m = Maquina.query.filter_by(serie=serie.upper(), activa=True).first()
    if not m:
        return jsonify({'error': 'No encontrada'}), 404
    return jsonify({
        'serie': m.serie,
        'punto': m.nombre_punto or m.zona or '—',
        'estado': m.estado_label(),
        'cobrador': m.cobrador_asignado.nombre if m.cobrador_asignado else 'Sin asignar'
    })
if __name__ == '__main__':
    print('EcoPulse by MAGO Solutions arrancando...')
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
