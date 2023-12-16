import abc
import enum

from typing import Dict

from .. import config


class Capability(enum.Enum):
	ImageGeneration = enum.auto()
	ChatResponse = enum.auto()
	ResponderPick = enum.auto()
	CharacterCreation = enum.auto()



class Format(enum.Enum):
	Square = enum.auto()
	Landscape = enum.auto()
	Portrait = enum.auto()


def singleton(cls):
	return cls()


class AIProvider:
	options = {
		cap: []
		for name,cap in Capability._member_map_.items()
	}


	def __init_subclass__(cls,**kwargs):
		pass


	def __init__(self):
		self.config = config.get('service_config',{}).get(self.identifier,{})
		basecls = self.__class__.__base__
		for cap in self.capabilities:
			basecls.options[cap].append(self)
			#basecls.options.setdefault(cap,{})[self.identifier] = self



	@classmethod
	def __getitem__(cls,attr):
		return cls.options[attr]

	@abc.abstractmethod
	def create_image(self, keyword_prompt: list, keyword_prompt_negative: list, fulltext_prompt: str, imageformat: Format):
		pass

	@abc.abstractmethod
	def respond_chat(self, chat, messagelist, allow_functioncall=True):
		pass

from . import anydream, open_ai, getimg

AI: Dict[str, AIProvider] = {
	name: [provider for provider in AIProvider.options[cap] if provider.identifier == config['use_service'][name]][0]
	for name, cap in Capability._member_map_.items()
}
