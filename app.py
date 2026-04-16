from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'duty-room-secret-key-2025'

# Настройка базы данных для Render (PostgreSQL) или локально (SQLite)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///duty_room.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ==================== МОДЕЛИ ДАННЫХ ====================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    badge = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    department = db.Column(db.String(50))
    unit = db.Column(db.String(50))
    role = db.Column(db.String(20), default='user')
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

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
    assigned_unit = db.Column(db.String(100))
    registered_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Squad(db.Model):
    __tablename__ = 'squads'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(30))
    unit = db.Column(db.String(50))
    status = db.Column(db.String(20), default='available')
    location = db.Column(db.String(200))
    radio_channel = db.Column(db.Integer, default=1)

class RadioMessage(db.Model):
    __tablename__ = 'radio_messages'
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.Integer, default=1)
    sender = db.Column(db.String(100))
    sender_department = db.Column(db.String(50))
    message = db.Column(db.Text, nullable=False)
    is_urgent = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Wanted(db.Model):
    __tablename__ = 'wanted'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100))
    plate = db.Column(db.String(20))
    crime = db.Column(db.String(200))
    dangerous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    issued_date = db.Column(db.String(10))
    issued_by = db.Column(db.String(100))

# ==================== СПИСОК ПОДРАЗДЕЛЕНИЙ И НАРЯДОВ ====================

SQUADS_LIST = [
    # ППСП (Патрульно-постовая служба полиции)
    {'name': 'ППСП-1', 'type': 'pps', 'unit': 'ППСП', 'radio_channel': 1},
    {'name': 'ППСП-2', 'type': 'pps', 'unit': 'ППСП', 'radio_channel': 1},
    {'name': 'ППСП-3', 'type': 'pps', 'unit': 'ППСП', 'radio_channel': 1},
    # ДПС (Дорожно-патрульная служба)
    {'name': 'ДПС-1', 'type': 'dps', 'unit': 'ДПС', 'radio_channel': 2},
    {'name': 'ДПС-2', 'type': 'dps', 'unit': 'ДПС', 'radio_channel': 2},
    # Росгвардия
    {'name': 'ОВО-1', 'type': 'ovo', 'unit': 'Росгвардия (ОВО)', 'radio_channel': 3},
    {'name': 'ОМОН', 'type': 'omon', 'unit': 'Росгвардия (ОМОН)', 'radio_channel': 3},
    {'name': 'ОСН/СОБР', 'type': 'osn', 'unit': 'Росгвардия (ОСН/СОБР)', 'radio_channel': 3},
    # СОГ (Следственно-оперативная группа)
    {'name': 'СОГ', 'type': 'sog', 'unit': 'Следственный отдел', 'radio_channel': 4}
]

USERS_LIST = [
    # Дежурная часть
    {'badge': '001', 'name': 'Майоров Сергей Владимирович', 'position': 'Начальник дежурной смены', 'department': 'ДЧ', 'role': 'chief'},
    {'badge': '002', 'name': 'Капитанова Анна Сергеевна', 'position': 'Оперативный дежурный', 'department': 'ДЧ', 'role': 'operator'},
    {'badge': '003', 'name': 'Старлей Петр Иванович', 'position': 'Оперативный дежурный', 'department': 'ДЧ', 'role': 'operator'},
    {'badge': '004', 'name': 'Младший лейтенант Соколов', 'position': 'Помощник оперативного дежурного', 'department': 'ДЧ', 'role': 'dispatcher'},
    
    # ППСП
    {'badge': '101', 'name': 'Сержант Сидоров Алексей', 'position': 'Сотрудник ППСП', 'department': 'ППСП', 'unit': 'ППСП-1', 'role': 'user'},
    {'badge': '102', 'name': 'Лейтенант Козлов Дмитрий', 'position': 'Сотрудник ППСП', 'department': 'ППСП', 'unit': 'ППСП-1', 'role': 'user'},
    {'badge': '103', 'name': 'Прапорщик Морозов Иван', 'position': 'Сотрудник ППСП', 'department': 'ППСП', 'unit': 'ППСП-2', 'role': 'user'},
    {'badge': '104', 'name': 'Старшина Васильев Петр', 'position': 'Сотрудник ППСП', 'department': 'ППСП', 'unit': 'ППСП-2', 'role': 'user'},
    {'badge': '105', 'name': 'Младший сержант Новиков', 'position': 'Сотрудник ППСП', 'department': 'ППСП', 'unit': 'ППСП-3', 'role': 'user'},
    
    # ДПС
    {'badge': '201', 'name': 'Капитан Орлов Денис', 'position': 'Сотрудник ДПС', 'department': 'ДПС', 'unit': 'ДПС-1', 'role': 'user'},
    {'badge': '202', 'name': 'Лейтенант Волков Андрей', 'position': 'Сотрудник ДПС', 'department': 'ДПС', 'unit': 'ДПС-1', 'role': 'user'},
    {'badge': '203', 'name': 'Старший лейтенант Зайцев', 'position': 'Сотрудник ДПС', 'department': 'ДПС', 'unit': 'ДПС-2', 'role': 'user'},
    
    # Росгвардия (ОВО)
    {'badge': '301', 'name': 'Прапорщик Титов Артем', 'position': 'Сотрудник ОВО', 'department': 'Росгвардия', 'unit': 'ОВО-1', 'role': 'user'},
    {'badge': '302', 'name': 'Сержант Кузнецов Илья', 'position': 'Сотрудник ОВО', 'department': 'Росгвардия', 'unit': 'ОВО-1', 'role': 'user'},
    
    # Росгвардия (ОМОН)
    {'badge': '311', 'name': 'Майор Соболев Игорь', 'position': 'Боец ОМОН', 'department': 'Росгвардия', 'unit': 'ОМОН', 'role': 'user'},
    {'badge': '312', 'name': 'Капитан Громов Виктор', 'position': 'Боец ОМОН', 'department': 'Росгвардия', 'unit': 'ОМОН', 'role': 'user'},
    {'badge': '313', 'name': 'Лейтенант Медведев', 'position': 'Боец ОМОН', 'department': 'Росгвардия', 'unit': 'ОМОН', 'role': 'user'},
    
    # Росгвардия (ОСН/СОБР)
    {'badge': '321', 'name': 'Подполковник Воронов', 'position': 'Боец ОСН/СОБР', 'department': 'Росгвардия', 'unit': 'ОСН/СОБР', 'role': 'user'},
    {'badge': '322', 'name': 'Майор Лисицын', 'position': 'Боец ОСН/СОБР', 'department': 'Росгвардия', 'unit': 'ОСН/СОБР', 'role': 'user'},
    
    # СОГ (Следственный отдел)
    {'badge': '401', 'name': 'Советник юстиции Белов', 'position': 'Следователь', 'department': 'Следственный отдел', 'unit': 'СОГ', 'role': 'user'},
    {'badge': '402', 'name': 'Юрист 1 класса Соловьева', 'position': 'Следователь', 'department': 'Следственный отдел', 'unit': 'СОГ', 'role': 'user'},
    
    # Следственный комитет
    {'badge': '411', 'name': 'Майор юстиции Кравцов', 'position': 'Следователь (СК)', 'department': 'Следственный комитет', 'unit': 'СОГ', 'role': 'user'},
    {'badge': '412', 'name': 'Капитан юстиции Новикова', 'position': 'Следователь (СК)', 'department': 'Следственный комитет', 'unit': 'СОГ', 'role': 'user'},
    
    # Дознание
    {'badge': '421', 'name': 'Лейтенант внутренней службы', 'position': 'Дознаватель', 'department': 'Дознание', 'unit': 'СОГ', 'role': 'user'},
    
    # Оперативный отдел
    {'badge': '431', 'name': 'Майор полиции Соколов', 'position': 'Оперуполномоченный', 'department': 'Оперативный отдел', 'unit': 'СОГ', 'role': 'user'},
    {'badge': '432', 'name': 'Капитан полиции Рыбакова', 'position': 'Оперуполномоченный', 'department': 'Оперативный отдел', 'unit': 'СОГ', 'role': 'user'},
    
    # Прокуратура
    {'badge': '501', 'name': 'Советник юстиции Агафонов', 'position': 'Прокурор', 'department': 'Прокуратура', 'unit': 'Иное', 'role': 'user'},
    {'badge': '502', 'name': 'Младший советник юстиции', 'position': 'Помощник прокурора', 'department': 'Прокуратура', 'unit': 'Иное', 'role': 'user'},
    
    # ФСБ
    {'badge': '601', 'name': 'Полковник Баранов', 'position': 'Сотрудник ФСБ', 'department': 'УФСБ', 'unit': 'Иное', 'role': 'user'},
    
    # Другие
    {'badge': '901', 'name': 'Сотрудник администрации', 'position': 'Представитель администрации', 'department': 'Администрация', 'unit': 'Иное', 'role': 'user'},
]

# ==================== СОЗДАНИЕ БАЗЫ ДАННЫХ ====================

with app.app_context():
    db.drop_all()
    db.create_all()
    
    # Создание нарядов
    for squad_data in SQUADS_LIST:
        squad = Squad(
            name=squad_data['name'],
            type=squad_data['type'],
            unit=squad_data['unit'],
            status='available',
            location='На базе',
            radio_channel=squad_data['radio_channel']
        )
        db.session.add(squad)
    
    # Создание пользователей
    for user_data in USERS_LIST:
        user = User(
            badge=user_data['badge'],
            name=user_data['name'],
            position=user_data['position'],
            department=user_data['department'],
            unit=user_data.get('unit', user_data['department']),
            role=user_data['role']
        )
        db.session.add(user)
    
    # Тестовые вызовы КУСП
    test_kusp = [
        Kusp(number='КУСП-2025-0001', year=2025, sequence=1,
             received_date='2025-04-16', received_time='08:30',
             source_name='Иванов И.И.', source_phone='89001234567',
             incident_place='ул. Ленина, д. 10', incident_type='crime',
             incident_description='Кража из магазина', priority='high',
             status='completed', assigned_to='ППСП-1', registered_by='Капитанова А.С.'),
        Kusp(number='КУСП-2025-0002', year=2025, sequence=2,
             received_date='2025-04-16', received_time='10:15',
             source_name='Петрова Е.В.', source_phone='89007654321',
             incident_place='перекресток Ленина/Советская', incident_type='accident',
             incident_description='ДТП с пострадавшими', priority='urgent',
             status='assigned', assigned_to='ДПС-1', registered_by='Старлей Петр'),
        Kusp(number='КУСП-2025-0003', year=2025, sequence=3,
             received_date='2025-04-16', received_time='14:20',
             source_name='Сидоров П.П.', source_phone='89001112233',
             incident_place='ул. Советская, д. 5', incident_type='domestic',
             incident_description='Семейный скандал', priority='medium',
             status='in_progress', assigned_to='ОВО-1', registered_by='Майоров С.В.'),
    ]
    for k in test_kusp:
        db.session.add(k)
    
    # Тестовые ориентировки
    test_wanted = [
        Wanted(number='ОРИЕНТ-2025-0001', name='Сидоров Алексей Петрович',
               crime='ст. 105 УК РФ - убийство', dangerous=True,
               issued_by='Майоров С.В.', issued_date='2025-04-15'),
        Wanted(number='ОРИЕНТ-2025-0002', plate='А001АА178',
               crime='Угон транспортного средства', dangerous=False,
               issued_by='Капитанова А.С.', issued_date='2025-04-16'),
    ]
    for w in test_wanted:
        db.session.add(w)
    
    db.session.commit()
    
    print("=" * 50)
    print("✅ База данных дежурной части создана!")
    print("=" * 50)
    print("\n📋 ПОДРАЗДЕЛЕНИЯ И НАРЯДЫ:")
    for s in SQUADS_LIST:
        print(f"   🚔 {s['name']} - {s['unit']}")
    print("\n👥 СОТРУДНИКИ ДОБАВЛЕНЫ:")
    for u in USERS_LIST[:10]:
        print(f"   {u['badge']} - {u['name']} ({u['position']})")
    print(f"   ... и еще {len(USERS_LIST)-10} сотрудников")
    print("\n🔑 ДЛЯ ВХОДА используйте табельный номер (например, 001, 101, 201, 301...)")
    print("=" * 50)

# ==================== ФУНКЦИИ ====================

def generate_kusp_number():
    year = datetime.now().year
    last = Kusp.query.filter_by(year=year).order_by(Kusp.sequence.desc()).first()
    seq = (last.sequence + 1) if last else 1
    return f"КУСП-{year}-{seq:04d}", year, seq

def generate_wanted_number():
    year = datetime.now().year
    last = Wanted.query.filter(Wanted.number.like(f"ОРИЕНТ-{year}-%")).order_by(Wanted.id.desc()).first()
    if last:
        num = int(last.number.split('-')[-1]) + 1
    else:
        num = 1
    return f"ОРИЕНТ-{year}-{num:04d}"

# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    user_badge = session.get('user_badge')
    if not user_badge:
        return redirect(url_for('login'))
    user = User.query.filter_by(badge=user_badge).first()
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
            user.last_seen = datetime.utcnow()
            db.session.commit()
            socketio.emit('user_status', {'badge': badge, 'name': user.name, 
                                          'department': user.department, 'status': 'online'})
            return redirect(url_for('index'))
        flash('Сотрудник с таким табельным номером не найден', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    badge = session.get('user_badge')
    if badge:
        user = User.query.filter_by(badge=badge).first()
        if user:
            user.is_online = False
            db.session.commit()
            socketio.emit('user_status', {'badge': badge, 'name': user.name,
                                          'department': user.department, 'status': 'offline'})
    session.clear()
    return redirect(url_for('login'))

# ==================== API ====================

@app.route('/api/kusp')
def api_kusp():
    status = request.args.get('status', 'all')
    query = Kusp.query
    if status != 'all':
        query = query.filter_by(status=status)
    kusp_list = query.order_by(Kusp.created_at.desc()).limit(100).all()
    return jsonify([{
        'id': k.id, 'number': k.number, 'received': f"{k.received_date} {k.received_time}",
        'source': k.source_name, 'phone': k.source_phone, 'place': k.incident_place,
        'type': k.incident_type, 'priority': k.priority, 'status': k.status,
        'assigned_to': k.assigned_to
    } for k in kusp_list])

@app.route('/api/kusp/<int:id>')
def api_kusp_detail(id):
    k = Kusp.query.get_or_404(id)
    return jsonify({
        'id': k.id, 'number': k.number, 'received_date': k.received_date,
        'received_time': k.received_time, 'source_name': k.source_name,
        'source_phone': k.source_phone, 'incident_place': k.incident_place,
        'incident_type': k.incident_type, 'incident_description': k.incident_description,
        'priority': k.priority, 'status': k.status, 'assigned_to': k.assigned_to,
        'assigned_unit': k.assigned_unit, 'registered_by': k.registered_by
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
        incident_description=data.get('incident_description'),
        priority=data.get('priority', 'medium'),
        registered_by=session.get('user_name', 'Система')
    )
    db.session.add(kusp)
    db.session.commit()
    socketio.emit('new_kusp', {'id': kusp.id, 'number': kusp.number, 'place': kusp.incident_place})
    return jsonify({'success': True, 'id': kusp.id, 'number': kusp.number})

@app.route('/api/kusp/<int:id>/assign', methods=['POST'])
def api_kusp_assign(id):
    kusp = Kusp.query.get_or_404(id)
    data = request.json
    kusp.assigned_to = data.get('assigned_to')
    kusp.assigned_unit = data.get('assigned_unit')
    kusp.status = 'assigned'
    db.session.commit()
    socketio.emit('kusp_assigned', {'id': kusp.id, 'number': kusp.number, 
                                    'assigned_to': kusp.assigned_to})
    return jsonify({'success': True})

@app.route('/api/kusp/<int:id>/status', methods=['POST'])
def api_kusp_status(id):
    kusp = Kusp.query.get_or_404(id)
    data = request.json
    kusp.status = data.get('status')
    if kusp.status == 'completed':
        kusp.assigned_to = None
    db.session.commit()
    socketio.emit('kusp_update', {'id': kusp.id, 'number': kusp.number, 'status': kusp.status})
    return jsonify({'success': True})

@app.route('/api/squads')
def api_squads():
    squads = Squad.query.all()
    return jsonify([{
        'id': s.id, 'name': s.name, 'type': s.type, 'unit': s.unit,
        'status': s.status, 'location': s.location, 'radio_channel': s.radio_channel
    } for s in squads])

@app.route('/api/squads/<int:id>/status', methods=['POST'])
def api_squad_status(id):
    squad = Squad.query.get_or_404(id)
    data = request.json
    squad.status = data.get('status')
    squad.location = data.get('location', squad.location)
    db.session.commit()
    socketio.emit('squad_update', {'id': squad.id, 'name': squad.name, 
                                   'status': squad.status, 'location': squad.location})
    return jsonify({'success': True})

@app.route('/api/radio/messages')
def api_radio_messages():
    channel = request.args.get('channel', 1, type=int)
    messages = RadioMessage.query.filter_by(channel=channel).order_by(
        RadioMessage.timestamp.desc()).limit(50).all()
    return jsonify([{
        'id': m.id, 'sender': m.sender, 'sender_department': m.sender_department,
        'message': m.message, 'is_urgent': m.is_urgent,
        'time': m.timestamp.strftime('%H:%M:%S')
    } for m in reversed(messages)])

@socketio.on('radio_message')
def handle_radio_message(data):
    user = User.query.filter_by(badge=session.get('user_badge')).first()
    msg = RadioMessage(
        channel=data.get('channel', 1),
        sender=user.name if user else 'Аноним',
        sender_department=user.department if user else 'Неизвестно',
        message=data.get('message'),
        is_urgent=data.get('is_urgent', False)
    )
    db.session.add(msg)
    db.session.commit()
    emit('radio_message', {
        'id': msg.id, 'sender': msg.sender, 'sender_department': msg.sender_department,
        'message': msg.message, 'is_urgent': msg.is_urgent,
        'time': msg.timestamp.strftime('%H:%M:%S')
    }, broadcast=True, room=f'channel_{msg.channel}')

@socketio.on('join_channel')
def handle_join_channel(data):
    channel = data.get('channel', 1)
    join_room(f'channel_{channel}')

@app.route('/api/wanted')
def api_wanted():
    wanted = Wanted.query.filter_by(status='active').all()
    return jsonify([{
        'id': w.id, 'number': w.number, 'name': w.name, 'plate': w.plate,
        'crime': w.crime, 'dangerous': w.dangerous
    } for w in wanted])

@app.route('/api/wanted/new', methods=['POST'])
def api_wanted_new():
    data = request.json
    number = generate_wanted_number()
    wanted = Wanted(
        number=number, name=data.get('name'), plate=data.get('plate'),
        crime=data.get('crime'), dangerous=data.get('dangerous', False),
        issued_date=datetime.now().strftime('%Y-%m-%d'),
        issued_by=session.get('user_name', 'Система')
    )
    db.session.add(wanted)
    db.session.commit()
    socketio.emit('new_wanted', {'id': wanted.id, 'name': wanted.name, 'number': wanted.number})
    return jsonify({'success': True, 'number': number})

@app.route('/api/wanted/<int:id>/capture', methods=['POST'])
def api_wanted_capture(id):
    wanted = Wanted.query.get_or_404(id)
    wanted.status = 'captured'
    db.session.commit()
    socketio.emit('wanted_captured', {'id': wanted.id, 'name': wanted.name})
    return jsonify({'success': True})

@app.route('/api/stats')
def api_stats():
    today = datetime.now().strftime('%Y-%m-%d')
    stats = {
        'kusp_today': Kusp.query.filter_by(received_date=today).count(),
        'kusp_active': Kusp.query.filter(Kusp.status.in_(['registered', 'assigned', 'in_progress'])).count(),
        'online_users': User.query.filter_by(is_online=True).count(),
        'available_squads': Squad.query.filter_by(status='available').count(),
        'wanted_active': Wanted.query.filter_by(status='active').count()
    }
    return jsonify(stats)

@app.route('/api/online_users')
def api_online_users():
    users = User.query.filter_by(is_online=True).all()
    return jsonify([{
        'badge': u.badge, 'name': u.name, 'position': u.position,
        'department': u.department, 'unit': u.unit
    } for u in users])

@app.route('/api/user_info')
def api_user_info():
    badge = session.get('user_badge')
    user = User.query.filter_by(badge=badge).first()
    if user:
        return jsonify({
            'badge': user.badge, 'name': user.name, 'position': user.position,
            'department': user.department, 'unit': user.unit, 'role': user.role
        })
    return jsonify({'error': 'Not logged in'}), 401

@socketio.on('connect')
def handle_connect():
    badge = session.get('user_badge')
    if badge:
        user = User.query.filter_by(badge=badge).first()
        if user:
            user.is_online = True
            db.session.commit()
            emit('user_status', {'badge': badge, 'name': user.name,
                                 'department': user.department, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    badge = session.get('user_badge')
    if badge:
        user = User.query.filter_by(badge=badge).first()
        if user:
            user.is_online = False
            db.session.commit()
            emit('user_status', {'badge': badge, 'name': user.name,
                                 'department': user.department, 'status': 'offline'}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)