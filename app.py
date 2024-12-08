from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import pika
from pymongo import MongoClient
from datetime import datetime
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

#refactor this and put it in the class (Task maybe)
def send_message(message):
    connection = pika.BlockingConnection(pika.ConnectionParameters('mq'))
    channel = connection.channel()
    channel.queue_declare(queue='task_queue')
    channel.basic_publish(exchange='', routing_key='task_queue', body=message)
    connection.close()
#refactor this and put it in the class (Task maybe)

client = MongoClient('nosql', 27017)
mongo_db = client['task_history']
history_collection = mongo_db['history']

def log_history(action, task_id):
    history_collection.insert_one({
        'action': action,
        'task_id': task_id,
        'timestamp': datetime.utcnow()
    })

class Task(db.Model):
    __tablename__ = 'task'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Open')
    # created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

@app.route('/')
def index():
    tasks = Task.query.all()
    tasks_list = [f"{task.id}. {task.title} - {task.status}" for task in tasks]
    return '<br>'.join(tasks_list)

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.json  #data comes in JSON format
    task = Task(
        title=data['title'],
        description=data.get('description', ''),
        status=data.get('status', 'Open')
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"message": "Task created", "task": task.id}), 201


@app.route('/add')
def add_task():
    task = Task(title='Sample Task', description='This is a sample task.')
    db.session.add(task)
    db.session.commit()
    send_message(f"Task {task.id} created.")
    log_history('create', task.id)
    return "Task added!"

@app.route('/analytics')
def analytics():
    query = text("""
        SELECT status, COUNT(*) as count
        FROM task
        GROUP BY status
    """)
    result = db.session.execute(query)
    analytics_data = {row.status: row.count for row in result.mappings()}
    return str(analytics_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)