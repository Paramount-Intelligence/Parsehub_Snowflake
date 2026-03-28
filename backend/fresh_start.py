#!/usr/bin/env python
"""Fresh Flask startup script - bypasses bytecode cache"""

import sys
import os

# CRITICAL: Set these BEFORE importing anything else
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True

# Clear any cached modules related to our app
modules_to_clear = [m for m in sys.modules.keys() if 'src.' in m or 'api_server' in m or 'batch_routes' in m]
for m in modules_to_clear:
    del sys.modules[m]

# Now import and run
os.chdir('d:/Parsehub-Snowflake/Parsehub_Snowflake/backend')
sys.path.insert(0, 'd:/Parsehub-Snowflake/Parsehub_Snowflake/backend')

from src.api.api_server import app

if __name__ == '__main__':
    print("Starting Flask with fresh bytecode...")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
