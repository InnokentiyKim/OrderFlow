#!/bin/sh
# Creates all Kafka topics required by OrderFlow.
# Runs once after the broker is healthy; idempotent (--if-not-exists).

set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

echo "Bootstrap server: $BOOTSTRAP"
echo "Creating Kafka topics..."

kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
  --topic order.events \
  --partitions 4 \
  --replication-factor 1

kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
  --topic inventory.commands \
  --partitions 4 \
  --replication-factor 1

kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
  --topic payment.commands \
  --partitions 4 \
  --replication-factor 1

kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
  --topic order.dlq \
  --partitions 1 \
  --replication-factor 1

echo "All topics created (or already existed)."
kafka-topics --bootstrap-server "$BOOTSTRAP" --list

