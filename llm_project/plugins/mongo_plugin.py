from pymongo import MongoClient
from utilities import config
import pandas as pd
from bson.objectid import ObjectId

class MongoPlugin():

    def __init__(self):
        pass

    def initilise_mongo_connection(self):
        self.client = MongoClient('mongodb://%s:%s@%s:%s/?directConnection=true' % (self.user, self.password, self.host, self.port))

    def get_collection(self, plant=None):
        from company.models import Plant, DatabaseConfigurations
        try:
            db_config = DatabaseConfigurations.objects.get(plant=plant)
            self.host = db_config.host
            self.port = db_config.port
            self.database = db_config.database_name
            self.user = db_config.user
            self.password = db_config.password
            self.initilise_mongo_connection()
            self.collection = db_config.collection
        except DatabaseConfigurations.DoesNotExist:
            self.host = config.MONGO_CONFIG['host']
            self.port = config.MONGO_CONFIG['port']
            self.database = config.MONGO_CONFIG['database']
            self.user = config.MONGO_CONFIG['user']
            self.password = config.MONGO_CONFIG['password']
            self.initilise_mongo_connection()
            self.collection = config.MONGO_CONFIG['collection']
        return self.client[self.database][self.collection]
    
    
    #==================================
    # USER CHAT COLLECTION
    #==================================
    def get_chat_collection(self):
        self.host = config.MONGO_CONFIG['host']
        self.port = config.MONGO_CONFIG['port']
        self.database = config.MONGO_CONFIG['database']
        self.user = config.MONGO_CONFIG['user']
        self.password = config.MONGO_CONFIG['password']
        self.initilise_mongo_connection()
        self.chat_collection = config.MONGO_CONFIG['chat_collection']
        return self.client[self.database][self.chat_collection]
    


    #==================================
    # ACCESS CPL DATA COLLECTION
    #==================================
    def get_cpl_collection(self):
        self.host = config.MONGO_CONFIG['host']
        self.port = config.MONGO_CONFIG['port']
        self.database = config.MONGO_CONFIG['database']
        self.user = config.MONGO_CONFIG['user']
        self.password = config.MONGO_CONFIG['password']
        self.initilise_mongo_connection()
        self.cpl_data_collection = config.MONGO_CONFIG['cpl_data_collection']
        return self.client[self.database][self.cpl_data_collection]
    

    def get_sensor_data(self, codes, collection, limit=10, start_date=None, end_date=None):
        data, query = {}, {}
        if start_date and end_date:
            query['device_timestamp'] = {
                '$gte': start_date, 
                '$lte': end_date
            }
        for code in codes:
            query['uuid'] = code
            sensor_data = collection.find(
                query, 
                # {'_id': False}
                ).sort('device_timestamp', -1).limit(limit)
            sensor_data = list(sensor_data)
            if sensor_data:
                df = pd.DataFrame(sensor_data)
                df['device_timestamp'] = df['device_timestamp'].dt.tz_localize('UTC')
                df['device_timestamp'] = df['device_timestamp'].dt.tz_convert(config.TIMEZONE)
                data[code] = df.to_dict('records')
        return data
    
    def update_data(self, collection, query, update_values, upsert=False):
        """
        Update a document in the MongoDB collection using the find and update method.
        :param collection: The name of the MongoDB collection
        :param query: The filter query to find the document to update
        :param update_values: The values to update in the document
        :param upsert: If true, insert the document if it does not exist
        :return: The updated document
        """
        # collection_obj = self.get_collection(collection)
        query['_id'] = ObjectId(query['_id'])
        result = collection.find_one_and_update(
            query,
            {'$set': update_values},
            return_document=True,
            upsert=upsert
        )
        return result
    
    def delete_data(self, ids):
        collection = self.get_collection()
        result = collection.delete_many({'_id': {'$in': ids}})
        return result


    def get_data(self, uuid_list, collection, limit=10, start_date=None, end_date=None, page_number=1, document_id=None, sort=-1):
        query = {}
        if document_id:
            query['_id'] = ObjectId(document_id)

        if start_date and end_date:
            query['device_timestamp'] = {'$gte': start_date, '$lte': end_date}

        if uuid_list:
            query['uuid'] = {'$in': uuid_list}

        skip = (page_number - 1) * limit
        sensor_data_cursor = collection.find(query).sort('device_timestamp', sort).skip(skip).limit(limit)
        sensor_data = list(sensor_data_cursor)

        if sensor_data:
            sensor_data = pd.json_normalize(sensor_data)
            sensor_data['_id'] = sensor_data['_id'].apply(str)
            sensor_data['device_timestamp'] = pd.to_datetime(sensor_data['device_timestamp'])
            sensor_data['device_timestamp'] = sensor_data['device_timestamp'].dt.tz_localize('UTC')
            sensor_data['device_timestamp'] = sensor_data['device_timestamp'].dt.tz_convert(config.TIMEZONE)

            return sensor_data.to_dict('records')

        return []
    
mongo_plugin = MongoPlugin()
collection = mongo_plugin.get_collection()
chat_collection = mongo_plugin.get_chat_collection()
cpl_data_collection = mongo_plugin.get_cpl_collection()
