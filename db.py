from flask_pymongo import PyMongo

mongo = PyMongo()

def init_db(app):
    """Initialize MongoDB with the Flask app"""
    mongo.init_app(app)

def get_collection(name):
    """Get a MongoDB collection"""
    return mongo.db[name]
