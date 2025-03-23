class FormatErrorCode:
	OK								= 0
	
	NO_TITLE						= 100
	TITLE_WRONG_TYPE				= 101
	
	NO_AUTHOR						= 200
	AUTHOR_WRONG_TYPE				= 201
	
	NO_QUESTIONS					= 300
	QUESTIONS_WRONG_TYPE			= 301
	EMPTY_QUESTIONS					= 302
	
	QUESTION_WRONG_TYPE				= 3000
	
	QUESTION_NO_VID					= 3100
	QUESTION_VID_WRONG_TYPE			= 3101
	QUESTION_EMPTY_VID				= 3102
	
	QUESTION_NO_TITLE				= 3200
	QUESTION_TITLE_WRONG_TYPE		= 3201
	QUESTION_EMPTY_TITLE			= 3202
	
	QUESTION_NO_PARTS				= 3300
	QUESTION_PARTS_WRONG_TYPE		= 3301
	QUESTION_EMPTY_PARTS			= 3302
	
	QUESTION_PART_WRONG_TYPE		= 33000
	QUESTION_PART_WRONG_LEN			= 33001
	QUESTION_PART_WRONG_TIME_TYPE	= 33002
	
	QUESTION_NO_CANDIDATES			= 3400
	QUESTION_CANDIDATES_WRONG_TYPE	= 3401
	QUESTION_EMPTY_CANDIDATES		= 3402
	
	QUESTION_CANDIDATE_WRONG_TYPE	= 34000
	QUESTION_EMPTY_CANDIDATE		= 34001
	
	NO_MISLEADINGS					= 400
	MISLEADINGS_WRONG_TYPE			= 401
	
	MISLEADING_WRONG_TYPE			= 4000
	EMPTY_MISLEADING				= 4001



def validateQuestionFormat(question_set):
	'''
	{
		"title": str,
		"author": str,
		"questions":
		[
			{
				"vid": str,
				"title": str			# for editor display
				"parts":
				[
					[ int, int ]		# [ start_time(ms), end_time(ms) ]
				],
				"candidates": [ str ],	# valid answers
			}
		],
		"misleadings": [ str ]	# misleading answers (can be empty list)
	}
	'''
	
	if "title" not in question_set:
		return FormatErrorCode.NO_TITLE
	if type(question_set["title"]) is not str:
		return FormatErrorCode.TITLE_WRONG_TYPE
		
	if "author" not in question_set:
		return FormatErrorCode.NO_AUTHOR
	if type(question_set["author"]) is not str:
		return FormatErrorCode.AUTHOR_WRONG_TYPE
		
	if "questions" not in question_set:
		return FormatErrorCode.NO_QUESTIONS
	if type(question_set["questions"]) is not list:
		return FormatErrorCode.QUESTIONS_WRONG_TYPE
	if len(question_set["questions"]) == 0:
		return FormatErrorCode.EMPTY_QUESTIONS
		
	for question in question_set["questions"]:
		if type(question) is not dict:
			return FormatErrorCode.QUESTION_WRONG_TYPE
			
		if "vid" not in question:
			return FormatErrorCode.QUESTION_NO_VID
		if type(question["vid"]) is not str:
			return FormatErrorCode.QUESTION_VID_WRONG_TYPE
		if len(question["vid"]) == 0:
			return FormatErrorCode.QUESTION_EMPTY_VID
				
		if "title" not in question:
			return FormatErrorCode.QUESTION_NO_TITLE
		if type(question["title"]) is not str:
			return FormatErrorCode.QUESTION_TITLE_WRONG_TYPE
		if len(question["title"]) == 0:
			return FormatErrorCode.QUESTION_EMPTY_TITLE
			
		if "parts" not in question:
			return FormatErrorCode.QUESTION_NO_PARTS
		if type(question["parts"]) is not list:
			return FormatErrorCode.QUESTION_PARTS_WRONG_TYPE
		if len(question["parts"]) == 0:
			return FormatErrorCode.QUESTION_EMPTY_PARTS
		for part in question["parts"]:
			if type(part) is not list:
				return FormatErrorCode.QUESTION_PART_WRONG_TYPE
			if len(part) != 2:
				return FormatErrorCode.QUESTION_PART_WRONG_LEN
			for i in range(2):
				if type(part[i]) is not int:
					return FormatErrorCode.QUESTION_PART_WRONG_TIME_TYPE
					
		if "candidates" not in question:
			return FormatErrorCode.QUESTION_NO_CANDIDATES
		if type(question["candidates"]) is not list:
			return FormatErrorCode.QUESTION_CANDIDATES_WRONG_TYPE
		if len(question["candidates"]) == 0:
			return FormatErrorCode.QUESTION_EMPTY_CANDIDATES
		for candidate in question["candidates"]:
			if type(candidate) is not str:
				return FormatErrorCode.QUESTION_CANDIDATE_WRONG_TYPE
			if len(candidate) == 0:
				return FormatErrorCode.QUESTION_EMPTY_CANDIDATE
			
	if "misleadings" not in question_set:
		return FormatErrorCode.NO_MISLEADINGS
	if type(question_set["misleadings"]) is not list:
		return FormatErrorCode.MISLEADINGS_WRONG_TYPE
	for option in question_set["misleadings"]:
		if type(option) is not str:
			return FormatErrorCode.MISLEADING_WRONG_TYPE
		if len(option) == 0:
			return FormatErrorCode.EMPTY_MISLEADING
	
	return FormatErrorCode.OK