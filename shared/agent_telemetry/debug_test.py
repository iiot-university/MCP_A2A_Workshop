#!/usr/bin/env python3
"""
Debug test for telemetry MQTT publishing.
This test publishes directly and verifies the message arrives.
"""

import json
import os
import sys
import time
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# Load environment
load_dotenv(project_root / ".env")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

print(f"MQTT_BROKER: {MQTT_BROKER}")
print(f"MQTT_PORT: {MQTT_PORT}")
print(f"MQTT_USERNAME: {MQTT_USERNAME}")
print(f"MQTT_PASSWORD: {'*' * len(MQTT_PASSWORD) if MQTT_PASSWORD else '(empty)'}")
print()

# Test topic
TEST_TOPIC = "Enterprise/Dallas/Agents/debug-test/Identity"

received_messages = []


def on_connect_pub(client, userdata, flags, reason_code, properties):
    print(f"[PUBLISHER] Connected with result: {reason_code}")


def on_publish(client, userdata, mid, reason_code, properties):
    print(f"[PUBLISHER] Message {mid} published, reason: {reason_code}")


def on_connect_sub(client, userdata, flags, reason_code, properties):
    print(f"[SUBSCRIBER] Connected with result: {reason_code}")
    client.subscribe("Enterprise/Dallas/Agents/#", qos=1)
    print(f"[SUBSCRIBER] Subscribed to Enterprise/Dallas/Agents/#")


def on_message(client, userdata, message):
    print(f"[SUBSCRIBER] Received on {message.topic}: {message.payload.decode()[:100]}")
    received_messages.append(message.topic)


def main():
    print("=" * 60)
    print("MQTT Telemetry Debug Test")
    print("=" * 60)
    print()

    # Create subscriber first
    print("Creating subscriber...")
    subscriber = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"debug-subscriber-{os.getpid()}",
        protocol=mqtt.MQTTv311,
    )
    subscriber.on_connect = on_connect_sub
    subscriber.on_message = on_message
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        subscriber.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    print(f"Subscriber connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    subscriber.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    subscriber.loop_start()
    time.sleep(2)  # Wait for subscription to be active
    
    # Create publisher
    print("\nCreating publisher...")
    publisher = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"debug-publisher-{os.getpid()}",
        protocol=mqtt.MQTTv311,
    )
    publisher.on_connect = on_connect_pub
    publisher.on_publish = on_publish
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        publisher.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    print(f"Publisher connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    publisher.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    publisher.loop_start()
    time.sleep(1)
    
    # Publish test message
    print(f"\nPublishing to: {TEST_TOPIC}")
    payload = json.dumps({
        "agent_id": "debug-test",
        "name": "Debug Test Agent",
        "timestamp": time.time(),
    })
    
    result = publisher.publish(TEST_TOPIC, payload, qos=1, retain=False)
    print(f"Publish result: rc={result.rc}, mid={result.mid}")
    
    # Wait for publish to complete
    result.wait_for_publish(timeout=5)
    print(f"Publish completed: is_published={result.is_published()}")
    
    # Wait for message to arrive at subscriber
    print("\nWaiting 3 seconds for message to arrive at subscriber...")
    time.sleep(3)
    
    # Check results
    print("\n" + "=" * 60)
    if TEST_TOPIC in received_messages:
        print("SUCCESS: Message was received by subscriber!")
    else:
        print("FAILURE: Message was NOT received by subscriber")
        print(f"Received topics: {received_messages}")
    print("=" * 60)
    
    # Cleanup
    publisher.loop_stop()
    publisher.disconnect()
    subscriber.loop_stop()
    subscriber.disconnect()


if __name__ == "__main__":
    main()
