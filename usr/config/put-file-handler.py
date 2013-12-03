#part-handler

import os
import re

def list_types():
    """
    Return a list of mime-types that are handled by this module
    """

    return(["text/plain"])

def handle_part(data,ctype,filename,payload):
    """
    data: the cloudinit object
    ctype: '__begin__', '__end__', or the specific mime-type of the part
    filename: the filename for the part, or dynamically generated part if
              no filename is given attribute is present
    payload: the content of the part (empty for begin or end)
    """

    if ctype == "__begin__":
       print "my handler is beginning"
       return
    if ctype == "__end__":
       print "my handler is ending"
       return

    print "==== received ctype=%s filename=%s ====" % (ctype,filename)

    first_line = payload.split('\n', 1)[0]
    match = re.search('#DestinationPath = (.+?)', first_line)
    if match:
      dest_path = match.group(1)
      d = os.path.dirname(dest_path)
      if (not os.path.exists(d)) & (d != ''):
        os.makedirs(d)

      with open(dest_path, 'w+') as f:
        for line in payload.splitlines():
          if not re.search('#DestinationPath = (.+?)', line):
            f.write(line)

    else:
      print "No DestinationPath found for the file %s" % filename

    print "==== end ctype=%s filename=%s" % (ctype, filename)