def validateQuestionFormat(question_set):
	'''
	{
		"title": str,
		"questions":
		[
			{
				"vid": str,
				"parts":
				[
					[ int, int ]		# [ start_time(ms), end_time(ms) ]
				],
				"candidates": [ str ],	# valid answers
				"title": str			# for editor display
			}
		],
		"misleadings": [ str ]	# misleading answers (can be empty list)
	}
	'''
	
	if "title" not in question_set:
		return 1
		
	if "questions" not in question_set:
		return 2
	if type(question_set["questions"]) is not list:
		return 3
	if len(question_set["questions"]) == 0:
		return 4
		
	for question in question_set["questions"]:
		if type(question) is not dict:
			return 100
			
		if "vid" not in question:
			return 101
		if type(question["vid"]) is not str:
			return 102
		if len(question["vid"]) == 0:
			return 103
			
		if "parts" not in question:
			return 104
		if type(question["parts"]) is not list:
			return 105
		if len(question["parts"]) == 0:
			return 106
		for part in question["parts"]:
			if type(part) is not list:
				return 150
			if len(part) != 2:
				return 151
			for i in range(2):
				if type(part[i]) is not int:
					return 200
					
		if "candidates" not in question:
			return 106
		if type(question["candidates"]) is not list:
			return 107
		if len(question["candidates"]) == 0:
			return 108
		for candidate in question["candidates"]:
			if type(candidate) is not str:
				return 250
			if len(candidate) == 0:
				return 251
				
		if "title" not in question:
			return 109
		if type(question["title"]) is not str:
			return 110
		if len(question["title"]) == 0:
			return 111
			
	if "misleadings" not in question_set:
		return 5
	if type(question_set["misleadings"]) is not list:
		return 6
	for option in question_set["misleadings"]:
		if type(option) is not str:
			return 300
		if len(option) == 0:
			return 301
	
	return 0