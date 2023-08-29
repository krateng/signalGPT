import sys
import os
import ruamel.yaml as yaml

from .classes import Session, Partner

yaml = yaml.YAML()
yaml.default_flow_style = False
yaml.representer.add_representer(str, lambda rep,node: rep.represent_scalar('tag:yaml.org,2002:str', node, style='|' if '\n' in node else None))


handle = sys.argv[1]

with Session() as session:
	p = session.query(Partner).where(Partner.handle==handle).first()
	filepath = os.path.join("contacts",handle + ".yml")



	if (not os.path.exists(filepath)) or (input("Overwrite? ").lower() == 'y'):
		with open(filepath,'w') as fd:
			yaml.dump({
				'name':p.name,
				'handle':p.handle,
				'bio':p.bio,
				'friend':p.friend,
				'color':p.color,
				'image':p.image,
				'instructions':p.instructions
			},fd)
