#!/bin/bash
cd /home/kavia/workspace/code-generation/dealer-management-system-197397-197406/dealers_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

