
''' buffer is circular ring buffer implemented to store  machine data received during network downtime'''

import os
from logConfig import *

FILENAME="BUFFER"
BUFFER_SIZE=0

if int(BUF_SIZE) > 10000:
#        print "size of buffer exceeded setting it to default"
        BUFFER_SIZE = 10000
else :
        BUFFER_SIZE=int(BUF_SIZE)

def string_conditioned(string):
    return string.decode('string_escape').rstrip() + '\n'
def pop():
    if os.stat(FILENAME).st_size > 0:
        with open(FILENAME, 'r+U') as fd:
            rows = fd.readlines()
        with open(FILENAME, 'w') as fd:
            n = int(1)
            fd.writelines(rows[n:])
            return ''.join(rows[:n])
    else:
        return "-1"
def empty():
	if os.stat(FILENAME).st_size >1:
		pass
	else:
		return -1


def trim_buffer(row):
    size = int(BUFFER_SIZE)
    with open(FILENAME, 'rU') as fd:
        rows = fd.readlines()
    num_rows = len(rows)
    if num_rows >= size:
        n = string_conditioned(row).count('\n')
#        pop(num_rows + n - size)
        pop()
def push(row):
    trim_buffer(row)
    with open(FILENAME, 'a') as fd:
        fd.write(string_conditioned(row))
    return ''
#Use push("string") print (pop().rstrip())
