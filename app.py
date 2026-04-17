from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'duty-room-secret-key-2025'

# Настройка базы данных
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///duty_room.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ==================== МОДЕЛИ ====================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    badge = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    department = db.Column(db.String(50))
    unit = db.Column(db.String(50))
    is_online = db.Column(db.Boolean, default=False)

class Kusp(db.Model):
    __tablename__ = 'kusp'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    year = db.Column(db.Integer, default=datetime.now().year)
    sequence = db.Column(db.Integer)
    received_date = db.Column(db.String(10), nullable=False)
    received_time = db.Column(db.String(8), nullable=False)
    source_name = db.Column(db.String(100))
    source_phone = db.Column(db.String(20))
    incident_place = db.Column(db.String(200), nullable=False)
    incident_type = db.Column(db.String(50))
    incident_description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='registered')
    assigned_to = db.Column(db.String(100))
    registered_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Squad(db.Model):
    __tablename__ = 'squads'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(50))
    status = db.Column(db.String(20), default='available')
    location = db.Column(db.String(200))
    radio_channel = db.Column(db.Integer, default=1)

class RadioMessage(db.Model):
    __tablename__ = 'radio_messages'
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.Integer, default=1)
    sender = db.Column(db.String(100))
    message = db.Column(db.Text, nullable=False)
    is_urgent = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Wanted(db.Model):
    __tablename__ = 'wanted'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100))
    crime = db.Column(db.String(200))
    dangerous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    issued_date = db.Column(db.String(10))

# ==================== СОЗДАНИЕ БАЗЫ ====================

with app.app_context():
    db.drop_all()
    db.create_all()
    
    # Пользователи
    users = [
        User(badge='001', name='Рабец Сергей', position='Начальник ОМВД', department='ДЧ'),
        User(badge='002', name='Лыков Андрей', position='Заместитель нач. ОМВД по ООП', department='ДЧ'),
        User(badge='101', name='Яковлев А.', position='Инспектор ПДН', department='ППСП', unit='ППСП-1'),
        User(badge='102', name='Лейтенант Козлов', position='Сотрудник ППСП', department='ППСП', unit='ППСП-1'),
        User(badge='103', name='Прапорщик Морозов', position='Сотрудник ППСП', department='ППСП', unit='ППСП-2'),
        User(badge='201', name='Капитан Орлов', position='Сотрудник ДПС', department='ДПС', unit='ДПС-1'),
        User(badge='202', name='Лейтенант Волков', position='Сотрудник ДПС', department='ДПС', unit='ДПС-1'),
        User(badge='301', name='Прапорщик Титов', position='Сотрудник ОВО', department='Росгвардия', unit='ОВО-1'),
        User(badge='311', name='Майор Соболев', position='Боец ОМОН', department='Росгвардия', unit='ОМОН'),
        User(badge='321', name='Майор Воронов', position='Боец ОСН/СОБР', department='Росгвардия', unit='ОСН/СОБР'),
        User(badge='401', name='Майор юстиции Белов', position='Следователь', department='Следственный отдел', unit='СОГ'),
        User(badge='421', name='Лейтенант', position='Дознаватель', department='Дознание', unit='СОГ'),
        User(badge='431', name='Майор Соколов', position='Оперуполномоченный', department='Оперативный отдел', unit='СОГ'),
        User(badge='501', name='Советник юстиции', position='Прокурор', department='Прокуратура'),
        User(badge='601', name='Полковник Баранов', position='Сотрудник ФСБ', department='УФСБ'),
    ]
    db.session.add_all(users)
    
    # Наряды
    squads = [
        Squad(name='ППСП-1', unit='ППСП', status='available', location='На базе', radio_channel=1),
        Squad(name='ППСП-2', unit='ППСП', status='available', location='На базе', radio_channel=1),
        Squad(name='ДПС-1', unit='ДПС', status='available', location='На базе', radio_channel=2),
        Squad(name='ДПС-2', unit='ДПС', status='available', location='На базе', radio_channel=2),
        Squad(name='ОВО-1', unit='Росгвардия', status='available', location='На базе', radio_channel=3),
        Squad(name='ОМОН', unit='Росгвардия', status='available', location='На базе', radio_channel=3),
        Squad(name='ОСН/СОБР', unit='Росгвардия', status='available', location='На базе', radio_channel=3),
        Squad(name='СОГ', unit='Следственный отдел', status='available', location='На базе', radio_channel=4),
    ]
    db.session.add_all(squads)
    
    # Тестовые ориентировки
    wanted = [
        Wanted(number='ОРИЕНТ-2025-0001', name='Сидоров Алексей Петрович', crime='ст. 105 УК РФ - убийство', dangerous=True, issued_date='2025-04-15'),
        Wanted(number='ОРИЕНТ-2025-0002', name='А001АА178', crime='Угон транспортного средства', dangerous=False, issued_date='2025-04-16'),
    ]
    db.session.add_all(wanted)
    
    db.session.commit()
    print("✅ База данных создана!")

# ==================== ФУНКЦИИ ====================

def generate_kusp_number():
    year = datetime.now().year
    last = Kusp.query.filter_by(year=year).order_by(Kusp.sequence.desc()).first()
    seq = (last.sequence + 1) if last else 1
    return f"КУСП-{year}-{seq:04d}", year, seq

def generate_wanted_number():
    year = datetime.now().year
    last = Wanted.query.filter(Wanted.number.like(f"ОРИЕНТ-{year}-%")).order_by(Wanted.id.desc()).first()
    num = int(last.number.split('-')[-1]) + 1 if last else 1
    return f"ОРИЕНТ-{year}-{num:04d}"

# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    if not session.get('user_badge'):
        return redirect(url_for('login'))
    user = User.query.filter_by(badge=session['user_badge']).first()
    if not user:
        return redirect(url_for('login'))
    return render_template('index.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        badge = request.form.get('badge')
        user = User.query.filter_by(badge=badge).first()
        if user:
            session['user_badge'] = badge
            session['user_name'] = user.name
            user.is_online = True
            db.session.commit()
            socketio.emit('user_status', {'badge': badge, 'name': user.name, 'status': 'online'})
            return redirect(url_for('index'))
        flash('Сотрудник не найден', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    badge = session.get('user_badge')
    if badge:
        user = User.query.filter_by(badge=badge).first()
        if user:
            user.is_online = False
            db.session.commit()
            socketio.emit('user_status', {'badge': badge, 'name': user.name, 'status': 'offline'})
    session.clear()
    return redirect(url_for('login'))

# ==================== API ====================

@app.route('/api/kusp')
def api_kusp():
    kusp_list = Kusp.query.order_by(Kusp.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': k.id, 'number': k.number, 'received': f"{k.received_date} {k.received_time}",
        'source': k.source_name, 'phone': k.source_phone, 'place': k.incident_place,
        'priority': k.priority, 'status': k.status, 'assigned_to': k.assigned_to
    } for k in kusp_list])

@app.route('/api/kusp/<int:id>')
def api_kusp_detail(id):
    k = Kusp.query.get_or_404(id)
    return jsonify({
        'id': k.id, 'number': k.number, 'source_name': k.source_name,
        'source_phone': k.source_phone, 'incident_place': k.incident_place,
        'incident_description': k.incident_description, 'priority': k.priority,
        'status': k.status, 'assigned_to': k.assigned_to, 'registered_by': k.registered_by
    })

@app.route('/api/kusp/new', methods=['POST'])
def api_kusp_new():
    data = request.json
    number, year, seq = generate_kusp_number()
    kusp = Kusp(
        number=number, year=year, sequence=seq,
        received_date=data.get('received_date', datetime.now().strftime('%Y-%m-%d')),
        received_time=data.get('received_time', datetime.now().strftime('%H:%M')),
        source_name=data.get('source_name'), source_phone=data.get('source_phone'),
        incident_place=data.get('incident_place'), incident_type=data.get('incident_type'),
        incident_description=data.get('incident_description'), priority=data.get('priority', 'medium'),
        registered_by=session.get('user_name', 'Система')
    )
    db.session.add(kusp)
    db.session.commit()
    socketio.emit('new_kusp', {'number': kusp.number, 'place': kusp.incident_place})
    return jsonify({'success': True, 'id': kusp.id, 'number': kusp.number})

@app.route('/api/kusp/<int:id>/assign', methods=['POST'])
def api_kusp_assign(id):
    kusp = Kusp.query.get_or_404(id)
    data = request.json
    kusp.assigned_to = data.get('assigned_to')
    kusp.status = 'assigned'
    db.session.commit()
    socketio.emit('kusp_assigned', {'id': kusp.id, 'number': kusp.number, 'assigned_to': kusp.assigned_to})
    return jsonify({'success': True})

@app.route('/api/kusp/<int:id>/status', methods=['POST'])
def api_kusp_status(id):
    kusp = Kusp.query.get_or_404(id)
    kusp.status = request.json.get('status')
    db.session.commit()
    socketio.emit('kusp_update', {'id': kusp.id, 'number': kusp.number, 'status': kusp.status})
    return jsonify({'success': True})

@app.route('/api/squads')
def api_squads():
    squads = Squad.query.all()
    return jsonify([{
        'id': s.id, 'name': s.name, 'unit': s.unit,
        'status': s.status, 'location': s.location, 'radio_channel': s.radio_channel
    } for s in squads])

@app.route('/api/squads/<int:id>/status', methods=['POST'])
def api_squad_status(id):
    squad = Squad.query.get_or_404(id)
    squad.status = request.json.get('status')
    squad.location = request.json.get('location', squad.location)
    db.session.commit()
    socketio.emit('squad_update', {'id': squad.id, 'name': squad.name, 'status': squad.status})
    return jsonify({'success': True})

@app.route('/api/radio/messages')
def api_radio_messages():
    channel = request.args.get('channel', 1, type=int)
    messages = RadioMessage.query.filter_by(channel=channel).order_by(RadioMessage.timestamp.desc()).limit(50).all()
    return jsonify([{
        'id': m.id, 'sender': m.sender, 'message': m.message,
        'is_urgent': m.is_urgent, 'time': m.timestamp.strftime('%H:%M:%S')
    } for m in reversed(messages)])

@socketio.on('radio_message')
def handle_radio_message(data):
    user = User.query.filter_by(badge=session.get('user_badge')).first()
    msg = RadioMessage(
        channel=data.get('channel', 1),
        sender=user.name if user else 'Аноним',
        message=data.get('message'),
        is_urgent=data.get('is_urgent', False)
    )
    db.session.add(msg)
    db.session.commit()
    emit('radio_message', {
        'sender': msg.sender, 'message': msg.message,
        'is_urgent': msg.is_urgent, 'time': msg.timestamp.strftime('%H:%M:%S')
    }, broadcast=True, room=f'channel_{msg.channel}')

@socketio.on('join_channel')
def handle_join_channel(data):
    join_room(f'channel_{data.get("channel", 1)}')

@app.route('/api/wanted')
def api_wanted():
    wanted = Wanted.query.filter_by(status='active').all()
    return jsonify([{
        'id': w.id, 'number': w.number, 'name': w.name,
        'crime': w.crime, 'dangerous': w.dangerous
    } for w in wanted])

@app.route('/api/wanted/new', methods=['POST'])
def api_wanted_new():
    data = request.json
    number = generate_wanted_number()
    wanted = Wanted(
        number=number, name=data.get('name'), crime=data.get('crime'),
        dangerous=data.get('dangerous', False), issued_date=datetime.now().strftime('%Y-%m-%d')
    )
    db.session.add(wanted)
    db.session.commit()
    socketio.emit('new_wanted', {'name': wanted.name, 'number': wanted.number})
    return jsonify({'success': True})

@app.route('/api/wanted/<int:id>/capture', methods=['POST'])
def api_wanted_capture(id):
    wanted = Wanted.query.get_or_404(id)
    wanted.status = 'captured'
    db.session.commit()
    socketio.emit('wanted_captured', {'name': wanted.name})
    return jsonify({'success': True})

@app.route('/api/stats')
def api_stats():
    today = datetime.now().strftime('%Y-%m-%d')
    return jsonify({
        'kusp_today': Kusp.query.filter_by(received_date=today).count(),
        'kusp_active': Kusp.query.filter(Kusp.status.in_(['registered', 'assigned'])).count(),
        'online_users': User.query.filter_by(is_online=True).count(),
        'available_squads': Squad.query.filter_by(status='available').count(),
        'wanted_active': Wanted.query.filter_by(status='active').count()
    })

@app.route('/api/online_users')
def api_online_users():
    users = User.query.filter_by(is_online=True).all()
    return jsonify([{'badge': u.badge, 'name': u.name, 'position': u.position, 'department': u.department} for u in users])

@socketio.on('connect')
def handle_connect():
    badge = session.get('user_badge')
    if badge:
        user = User.query.filter_by(badge=badge).first()
        if user:
            user.is_online = True
            db.session.commit()
            emit('user_status', {'badge': badge, 'name': user.name, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    badge = session.get('user_badge')
    if badge:
        user = User.query.filter_by(badge=badge).first()
        if user:
            user.is_online = False
            db.session.commit()
            emit('user_status', {'badge': badge, 'name': user.name, 'status': 'offline'}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
