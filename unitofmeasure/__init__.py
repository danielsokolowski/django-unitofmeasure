import os
import sys

# Let's add our pint library to python path
PINT_ROOT = os.path.dirname(os.path.abspath(__file__)).replace('\\','/') # the replacements are for windows
PINT_ROOT = os.path.join(PINT_ROOT
						, 'danielsokolowski-pint').replace('\\','/') 
sys.path.insert(0, PINT_ROOT)
import pint

