#!/bin/bash
# Setup script to create .env file from .env.example

if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env file created from .env.example"
    echo "Please update .env with your actual configuration values"
else
    echo ".env file already exists"
fi

