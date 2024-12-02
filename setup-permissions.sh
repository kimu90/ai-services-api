#!/bin/bash

# Create script to set up permissions before starting containers
mkdir -p logs/neo4j logs/postgres logs/redis logs/api
sudo chown -R 1000:1001 logs
sudo chmod -R 770 logs
