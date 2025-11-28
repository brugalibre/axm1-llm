<h1>Api-Wrapper for AX-M1 LLM</h1>


<h1> Table of content</h1>
<lu>
  <li> 1. Summary </li>
  <li> 2. How to use it </li>
</lu>  

<h1> 1. Summary </h1>
This repository provides an api wrapper which allowes to communicate with an ax-m1 llm via a rest-api. It assumes that the model can be launched by a executable shell script
and the tokenizer with a python file. Besides that its all docker based and consists of two services resp. docker container:
<lu>
  <li> llm-service:
		Wrappes the actual llm-models, is responsible for starting the model and the tokenizer as well as monitoring the status of the model 
		(like initializing, processing prompt, outputting prompt and so on). 
		Provides a REST endpoint at port 11535 for retrieving information about prompt the model, get status or status transition information.
		Befor starting the model, the llm-service starts the tokenizer if it's not already running and awaits then the model initialization/readyness.
		After each prompt a .prom file is written for the model specific metrics.
  </li>
  <li> tokenizer-service: 
		Wrappes the tokenizer and provides a REST endpoint at port 8101 in order to start the tokenizer or get status informations
		The tokenizer-service also contains an api (main.py) which is more intended for internal use</li>
</lu>  



<h1>2. How to use it:</h1>
<lu>
  <li> 
	Download the model: <br>
		Models can be downloaded from huggingface directly or using the huggingface-cli within a python environment. Once the model is downloaded it has to be placed within the /model directory
		Lets take the deepseek-r1 8b model as an example. The folders may look like this: /model/deepseek-r1-8b/..
		In order to make the model accessible for the api-wraper the docker container needs to be restarted.
  </li>
  <li> 
	Prepare the model: <br>
	In order to use the model, the .sh-file needs to be executable and must contain `#!/bin/sh` on the first line
	Also the llm-service assume no continous output. The model thinks until is done and then output the answer in one hit. The .sh-file needs to be adjusted
  </li>
  <li> Configure the model descriptor: <br>
		If the model is downloaded and mapped into the docker container we need to provide some meta-information to the wrapper. This informations area added to the `/model/model-descriptor.json`
		For each model there should be an entry. Using `/app` as the working directory of the container a complete model/model-descriptor.json can look like this:
		<pre>
		[
		   {
			  "model_name":"deepseek-r1-7b",
			  "run_cmd":"./run-deepseek-r1-8b-4qt.sh",
			  "model_path":"/app/model/deepseek-r1-8b-4qt",
			  "include_thinking":"false",
			  "run_on_startup":"true",
			  "tokenizer_path":"/app/model/deepseek-r1-8b-4qt",
			  "tokenizer_py":"deepkseek-r1-tokenizer.py",
			  "tokenizer_port":"1234"
		   }
		]
		</pre>
		Please note that the model path can be different than the tokenizer path. If so, it has also to be reflected in the docker-compose.yaml like `./tokenizers:/app/models:ro` where 'tokenizers' contains the tokenizer files
  </li>
</lu>
