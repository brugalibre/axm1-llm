import json
import logging
from llmservice import LlmService
from tokenizerservice import TokenizerService

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

# Contains all available models (aka model-descriptors) as well as all running models (aka LlmService)
# At the moment the model-descriptors are cached, so adding new models require a restart of the docker services
class ModelHelper():


    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(ModelHelper, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.name_to_llm_services = {}
        self.name_to_tokenizer_services = {}
        self.model_descriptors = None

    def __read_model_descriptors(self):
        with open("/app/models/model-descriptors.json", "r") as file:
            self.model_descriptors = json.load(file)


    def create_tokenizer_services(self):
        if self.model_descriptors == None:
            self.__read_model_descriptors()
        for model_desc in self.model_descriptors:
            model_name = model_desc["model_name"]
            self.name_to_tokenizer_services.setdefault(model_name, TokenizerService(model_desc["tokenizer_py"],
                model_desc["tokenizer_path"], int(model_desc["tokenizer_port"])))
            logger.info(f"Created tokenizer-service for model '{model_name}'")

    def create_llm_services(self):
        if self.model_descriptors == None:
            self.__read_model_descriptors()
        for model_desc in self.model_descriptors:
            model_name = model_desc["model_name"]
            llm_service = LlmService(model_name, model_desc["run_cmd"], model_desc["model_path"], model_desc["tokenizer_ip"],
                 model_desc["tokenizer_py"], model_desc["tokenizer_path"], int(model_desc["tokenizer_port"]),
                 model_desc["include_thinking"])
            self.name_to_llm_services.setdefault(model_name, llm_service)
            logger.info(f"Created llm-service for model '{model_name}'")

    def start_default_llm_services(self):
        if self.model_descriptors is None:
            self.create_llm_services()
        for model_desc in self.model_descriptors:
            model_name = model_desc["model_name"]
            start_service = model_desc["run_on_startup"]
            if start_service.lower() == "true":
                llm_service = self.name_to_llm_services[model_name]
                logger.info(f"About to start llm-service '{model_name}' ({start_service})")
                llm_service.start_model()
                llm_service.await_readiness()

    def get_llmservice(self, model_name: str) -> LlmService:
        if model_name in self.name_to_llm_services:
            return self.name_to_llm_services[model_name]
        raise Exception(f"No model found for name '{model_name}'!")

    def get_tokenizerservice(self, model_name: str) -> TokenizerService:
        if model_name in self.name_to_tokenizer_services:
            return self.name_to_tokenizer_services[model_name]
        raise Exception(f"No tokenizer found for name '{model_name}'!")
