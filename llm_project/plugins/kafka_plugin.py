from confluent_kafka import Consumer


class KafkaMessageConsumer:
    def __init__(self, topic):
        self.consumer = Consumer({'bootstrap.servers': 'optiex_kafka:29092', 'group.id': 'mygroup'})
        self.consumer.subscribe([topic])
    
    def consume_messages(self):
        return self.consumer