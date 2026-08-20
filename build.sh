#!/usr/bin/env bash

pip install -r requirements.txt
alembic upgrade head
