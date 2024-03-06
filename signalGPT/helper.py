import os
import json
from datetime import datetime, timezone, timedelta

from signalGPT import config


def save_debug_file(category,data):
	os.makedirs("debug",exist_ok=True)

	with open(os.path.join("debug",category + ".json"),'w') as fd:
		json.dump(data,fd,indent=4)


def now():
	return int(datetime.now(timezone.utc).timestamp())


def describe_time(timestamp):
	time = datetime.fromtimestamp(timestamp,tz=timezone.utc)
	offset = timedelta(hours=config['user']['utc_offset'])
	local_time = time + offset
	return local_time.strftime('%A %B %d, %H:%M')