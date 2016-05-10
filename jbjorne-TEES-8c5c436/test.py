#!/usr/bin/env python

# when calling command line, we call classify with different options
# can be called classify(input,model,output)

# input needs to be in interaction XML?

from Detectors.Preprocessor import Preprocessor
from train import workdir, getDetector, getSteps
import os
import gzip
from classify import classify , getModel

import xml.etree.ElementTree as ET
import json

def mywrapper(input_text):
#	with open('working_file.txt','w') as f:
#		f.write(input_text)
		
#	myclassify('working_file.txt',"GE11",'output/output')
	
#	os.remove('working_file.txt')
	
	with gzip.open('output/output-pred.xml.gz') as f:
		pa = tees_to_pubannotation(f.read())
		print(pa)
	
def tees_to_pubannotation(input):
	
	root = ET.fromstring(input) # from parses directly into an Element
	text = root.find("document").get("text")
		
	pre_json = { "text" : text }
	pre_json["denotations"] = list()
	pre_json["relations"] = list()
	
	
	for token in root.findall(".//token"):
		token_dict = dict()
		token_dict["id"] = token.get("id")
		
		start_span , end_span = token.get("charOffset").split("-")
		token_dict["span"] = { "begin" : int(start_span) , "end" : int(end_span) }
		
		token_dict["obj"] = token.get("POS")
		
		pre_json["denotations"].append(token_dict)
	
	for dependency in root.findall(".//dependency"):
		relation_dict = dict()
		relation_dict["id"] = dependency.get("id")
		relation_dict["subj"] = dependency.get("t1")
		relation_dict["obj"] = dependency.get("t2")
		relation_dict["pred"] = dependency.get("type")
		
		pre_json["relations"].append(relation_dict)		
	return(json.dumps(pre_json,sort_keys=True,indent=4))

def myclassify(input,model,output):
	
	# Define processing steps
	selector, detectorSteps, omitDetectorSteps = getSteps(None, None, ["PREPROCESS", "CLASSIFY"])
	
	model = getModel(model)
	preprocessor = Preprocessor()
	
	classifyInput = preprocessor.process(input, (output + "-preprocessed.xml.gz"), None, model, [], fromStep=detectorSteps["PREPROCESS"], toStep=None, omitSteps=omitDetectorSteps["PREPROCESS"])
			
	detector = getDetector(None, model)[0]() # initialize detector object
	
	detector.bioNLPSTParams = detector.getBioNLPSharedTaskParams(None, model)
	
	detector.classify(classifyInput, model, output, fromStep=detectorSteps["CLASSIFY"], omitSteps=omitDetectorSteps["CLASSIFY"])
	



if __name__=="__main__":
	mywrapper("I saw the best minds of my generation destroyed by madness, starving hysterical naked, dragging themselves to the Negro streets at dawn looking for an angry fix.")