import os
import json

def save_debug_file(category,data):
	os.makedirs("debug",exist_ok=True)

	with open(os.path.join("debug",category + ".json"),'w') as fd:
		json.dump(data,fd,indent=4)
