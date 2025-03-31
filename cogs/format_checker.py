MAX_STR_LEN = 100

class FormatErrorCode:
	OK								= 0
	
	NO_TITLE						= 100
	TITLE_WRONG_TYPE				= 101
	TITLE_TOO_LONG					= 102
	
	NO_AUTHOR						= 200
	AUTHOR_WRONG_TYPE				= 201
	AUTHOR_TOO_LONG					= 202
	
	NO_QUESTIONS					= 300
	QUESTIONS_WRONG_TYPE			= 301
	EMPTY_QUESTIONS					= 302
	
	QUESTION_WRONG_TYPE				= 3000
	
	QUESTION_NO_VID					= 3100
	QUESTION_VID_WRONG_TYPE			= 3101
	QUESTION_WRONG_VID_FORMAT		= 3102
	
	QUESTION_NO_TITLE				= 3200
	QUESTION_TITLE_WRONG_TYPE		= 3201
	QUESTION_EMPTY_TITLE			= 3202
	QUESTION_TITLE_TOO_LONG			= 3203
	
	QUESTION_NO_PARTS				= 3300
	QUESTION_PARTS_WRONG_TYPE		= 3301
	QUESTION_EMPTY_PARTS			= 3302
	
	QUESTION_PART_WRONG_TYPE		= 33000
	QUESTION_PART_WRONG_LEN			= 33001
	QUESTION_PART_WRONG_TIME_TYPE	= 33002
	QUESTION_PART_INVALID_DURATION	= 33003
	
	QUESTION_NO_CANDIDATES			= 3400
	QUESTION_CANDIDATES_WRONG_TYPE	= 3401
	QUESTION_EMPTY_CANDIDATES		= 3402
	
	QUESTION_CANDIDATE_WRONG_TYPE	= 34000
	QUESTION_EMPTY_CANDIDATE		= 34001
	QUESTION_CANDIDATE_TOO_LONG		= 34002
	
	NO_MISLEADINGS					= 400
	MISLEADINGS_WRONG_TYPE			= 401
	
	MISLEADING_WRONG_TYPE			= 4000
	EMPTY_MISLEADING				= 4001
	MISLEADING_TOO_LONG				= 4002



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
	if len(question_set["title"]) > MAX_STR_LEN:
		return FormatErrorCode.TITLE_TOO_LONG
		
	if "author" not in question_set:
		return FormatErrorCode.NO_AUTHOR
	if type(question_set["author"]) is not str:
		return FormatErrorCode.AUTHOR_WRONG_TYPE
	if len(question_set["author"]) > MAX_STR_LEN:
		return FormatErrorCode.AUTHOR_TOO_LONG
		
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
		if len(question["vid"]) != 11 or not question["vid"].replace('_', '').replace('-', '').isalnum():
			return FormatErrorCode.QUESTION_WRONG_VID_FORMAT
				
		if "title" not in question:
			return FormatErrorCode.QUESTION_NO_TITLE
		if type(question["title"]) is not str:
			return FormatErrorCode.QUESTION_TITLE_WRONG_TYPE
		if len(question["title"]) == 0:
			return FormatErrorCode.QUESTION_EMPTY_TITLE
		if len(question["title"]) > MAX_STR_LEN:
			return FormatErrorCode.QUESTION_TITLE_TOO_LONG
			
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
			if type(part[0]) is not int or type(part[1]) is not int:
				return FormatErrorCode.QUESTION_PART_WRONG_TIME_TYPE
			if part[1] <= part[0]:
				return FormatErrorCode.QUESTION_PART_INVALID_DURATION
					
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
			if len(candidate) > MAX_STR_LEN:
				return FormatErrorCode.QUESTION_CANDIDATE_TOO_LONG
			
	if "misleadings" not in question_set:
		return FormatErrorCode.NO_MISLEADINGS
	if type(question_set["misleadings"]) is not list:
		return FormatErrorCode.MISLEADINGS_WRONG_TYPE
	for option in question_set["misleadings"]:
		if type(option) is not str:
			return FormatErrorCode.MISLEADING_WRONG_TYPE
		if len(option) == 0:
			return FormatErrorCode.EMPTY_MISLEADING
		if len(option) > MAX_STR_LEN:
			return FormatErrorCode.MISLEADING_TOO_LONG
	
	return FormatErrorCode.OK