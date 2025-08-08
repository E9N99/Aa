import os
import random
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room

# تحميل متغيرات البيئة
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

socketio = SocketIO(app, async_mode='eventlet')

# إعدادات Twilio
TWILIO_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_FROM = os.getenv('TWILIO_FROM_NUMBER')
OTP_EXPIRY = int(os.getenv('OTP_EXPIRY_SECONDS', '300'))

_twilio_client = None
if TWILIO_SID and TWILIO_TOKEN:
    try:
        from twilio.rest import Client
        _twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
    except Exception as e:
        print('Twilio init error:', e)

# تخزين مؤقت للـ OTP والرسائل (للشرح فقط)
OTP_STORE = {}  # رقم الهاتف -> {code, expires_at, sent}
CHAT_HISTORY = []

def generate_otp(length=6):
    range_start = 10**(length-1)
    range_end = (10**length) - 1
    return str(random.randint(range_start, range_end))

def send_sms(to_number, message):
    if _twilio_client:
        try:
            _twilio_client.messages.create(body=message, from_=TWILIO_FROM, to=to_number)
            return True
        except Exception as e:
            print('Twilio send failed:', e)
            return False
    else:
        print(f"[SMS MOCK] To: {to_number} | Message: {message}")
        return True

@app.route('/')
def index():
    if session.get('user_phone'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    phone = request.form.get('phone')
    if not phone:
        flash('يرجى إدخال رقم الهاتف')
        return redirect(url_for('index'))

    entry = OTP_STORE.get(phone, {'sent': 0})
    if entry.get('sent', 0) >= 10:
        flash('تم الوصول لحد الإرسال المسموح. حاول لاحقاً.')
        return redirect(url_for('index'))

    code = generate_otp(6)
    expires_at = time.time() + OTP_EXPIRY
    OTP_STORE[phone] = {'code': code, 'expires_at': expires_at, 'sent': entry.get('sent', 0) + 1}

    message = f'رمز التحقق هو: {code}. صالح لمدة {OTP_EXPIRY//60} دقيقة.'
    sent = send_sms(phone, message)
    if sent:
        session['pending_phone'] = phone
        return redirect(url_for('verify'))
    else:
        flash('فشل إرسال الرسالة النصية. تأكد من الإعدادات.')
        return redirect(url_for('index'))

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'GET':
        return render_template('verify.html')

    phone = session.get('pending_phone')
    if not phone:
        flash('الرجاء إدخال رقم الهاتف مجدداً')
        return redirect(url_for('index'))

    user_code = request.form.get('otp')
    record = OTP_STORE.get(phone)
    if not record:
        flash('لم يتم إرسال رمز أو انتهت صلاحيته')
        return redirect(url_for('index'))

    if time.time() > record['expires_at']:
        OTP_STORE.pop(phone, None)
        flash('انتهت صلاحية الرمز. أرسل رمز جديد.')
        return redirect(url_for('index'))

    if user_code == record['code']:
        session.pop('pending_phone', None)
        session['user_phone'] = phone
        OTP_STORE.pop(phone, None)
        return redirect(url_for('dashboard'))
    else:
        flash('رمز غير صحيح')
        return redirect(url_for('verify'))

@app.route('/dashboard')
def dashboard():
    if not session.get('user_phone'):
        return redirect(url_for('index'))
    return render_template('dashboard.html', phone=session.get('user_phone'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/chat_history')
def chat_history():
    if not session.get('user_phone'):
        return jsonify({'ok': False}), 403
    return jsonify({'ok': True, 'history': CHAT_HISTORY[-50:]})

@socketio.on('join')
def on_join(data):
    room = 'support_room'
    join_room(room)
    emit('status', {'msg': f"{data.get('user')} انضم الى الشات"}, room=room)

@socketio.on('message')
def handle_message(data):
    user = data.get('user')
    text = data.get('text')
    ts = datetime.utcnow().isoformat()
    msg = {'user': user, 'text': text, 'ts': ts}
    CHAT_HISTORY.append(msg)
    emit('message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
