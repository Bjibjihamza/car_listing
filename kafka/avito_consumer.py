from kafka import KafkaConsumer
import json

# ✅ Kafka Consumer Setup
consumer = KafkaConsumer(
    "avito_topic",  # Kafka topic to listen to
    bootstrap_servers="localhost:9092",
    auto_offset_reset="earliest",  # Start reading from the beginning
    enable_auto_commit=True,
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))  # Convert JSON messages
)

print("🚀 Kafka Consumer Started: Listening for new messages...")

# ✅ Read messages from Kafka and print them
for message in consumer:
    car_data = message.value  # Extract data from Kafka message
    print(f"📥 Received Data: {car_data}")
