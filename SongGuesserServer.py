import os

try:
	import websockets
except:
	os.system("pip3 install websockets")
	import websockets

import pathlib
import ssl
import asyncio
import json
import time
import random
import re



YT_VID_REGEX = r"v=([^\&\?\/]*)"
GAMESTEP = {
	"IDLE": 0,		# game not started yet
	"LOADING": 1,	# waiting for video to load
	"PLAYING": 2,	# guessing
	"WAITING": 3,	# counting down to play next part
	"CHECKING": 4	# someone or no one guessed the right answer, show the result and wait for the next part
}



# load video but not play yet
def GetLoadPacket(vid):
	return json.dumps({
		"type": "load",
		"vid": vid
	})
# play video at specified time
def GetPlayPacket(range):
	return json.dumps({
		"type": "play",
		"start": range[0],
		"end": range[1]
	})
# notify user the id of himself
def GetUserIDPacket(id):
	return json.dumps({
		"type": "uid",
		"id": id
	})
# user list
def GetUserListPacket(userlist):
	return json.dumps({
		"type": "userlist",
		"list": userlist
	})
# current question set
def GetQuestionSetPacket(data, set_count):
	subdata = None
	if data != None:
		candidates = set(data["interrupts"])
		for q in data["questions"]:
			for name in q["names"]:
				candidates.add(name)
		subdata = {
			"title": data["title"],
			"author": data["author"],
			"count": len(data["questions"]),
			"img": data["thumbnail"],
			"candidates": list(candidates)
		}
	return json.dumps({
		"type": "qset",
		"data": subdata,
		"count": set_count
	})
# current target question count
def GetQuestionCountPacket(set_count):
	return json.dumps({
		"type": "qcount",
		"count": set_count
	})
# current target question count
def GetGameStatePacket(question_number, part):
	return json.dumps({
		"type": "gstate",
		"qnum": question_number,
		"part": part
	})
# game start
def GetStartPacket():
	return json.dumps({
		"type": "start"
	})
# player guessed answer
def GetGuessPacket(uid, guess):
	return json.dumps({
		"type": "guess",
		"uid": uid,
		"guess": guess
	})
# player get score
def GetPlayerScorePacket(uid):
	return json.dumps({
		"type": "score",
		"uid": uid
	})
# reveal question answer
def GetRevealAnswerPacket(valid_answers):
	return json.dumps({
		"type": "reveal",
		"answers": valid_answers
	})
# game end show result
def GetShowResultPacket():
	return json.dumps({
		"type": "result"
	})

# validate question set format
def IsValidQuestionSet(data):
	if type(data) is not dict:
		return False
	if "title" not in data:
		return False
	if "questions" not in data:
		return False
	if type(data["questions"]) is not list:
		return False
	if len(data["questions"]) == 0:
		return False
	for q in data["questions"]:
		if type(q) is not dict:
			return False
		if "names" not in q:
			return False
		if type(q["names"]) is not list:
			return False
		if len(q["names"]) == 0:
			return False
		for name in q["names"]:
			if type(name) is not str:
				return False
			if len(name) == 0:
				return False
		if "vid" not in q:
			return False
		if "parts" not in q:
			return False
		if type(q["parts"]) is not list:
			return False
		if len(q["parts"]) == 0:
			return False
		for part in q["parts"]:
			if type(part) is not list:
				return False
			if len(part) != 2:
				return False
			if type(part[0]) is not float or type(part[0]) is not int:
				return False
			if type(part[1]) is not float or type(part[1]) is not int:
				return False
	if "interrupts" not in data:
		return False
	if type(data["interrupts"]) is not list:
		return False
	for v in data["interrupts"]:
		if type(v) is not str:
			return False
	return True



user_idx = 0
game_data = {
	"game_step": GAMESTEP["IDLE"],
	"question_set": None,
	"question_count": 10,
	"question_pool": None,
	"current_question": None,
	"current_question_part": -1,
	"current_question_count": -1
}


USERS = dict()
async def process(websocket, path):
	global user_idx
	
	async def PlayQuestionPart():
		part = game_data["current_question_part"]
		packet = GetPlayPacket(game_data["current_question"]["parts"][part])
		await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
	
	async def CheckNextQuestion():
		game_data["current_question_count"] += 1
		if game_data["current_question_count"] == game_data["question_count"]:
			# broadcast show result
			packet = GetShowResultPacket()
			await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
			
			game_data["game_step"] = GAMESTEP["IDLE"]
			game_data["current_question"] = None
			game_data["current_question_part"] = -1
			game_data["current_question_count"] = -1
		else:
			await LoadRandomQuestion()
			
		packet = GetGameStatePacket(game_data["current_question_count"], game_data["current_question_part"])
		await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
		
	async def CheckQuestionNextPart():
		game_data["current_question_part"] += 1
		if game_data["current_question_part"] >= len(game_data["current_question"]["parts"]):
			# broadcast reveal answer
			packet = GetRevealAnswerPacket(game_data["current_question"]["names"])
			await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
			await CheckNextQuestion()
		else:
			game_data["game_step"] = GAMESTEP["WAITING"]
			packet = GetGameStatePacket(game_data["current_question_count"], game_data["current_question_part"])
			await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
			await asyncio.sleep(3)
			game_data["game_step"] = GAMESTEP["PLAYING"]
			await PlayQuestionPart()
	
	async def LoadRandomQuestion():
		if len(game_data["question_pool"]) == 0:
			return
			
		target = random.randint(0, len(game_data["question_pool"]) - 1)
		game_data["question_pool"][target], game_data["question_pool"][-1] = game_data["question_pool"][-1], game_data["question_pool"][target]
		game_data["current_question"] = game_data["question_pool"].pop()
		game_data["current_question"]["names"] = set(game_data["current_question"]["names"])
		game_data["current_question_part"] = -1
		game_data["game_step"] = GAMESTEP["LOADING"]
		
		packet = GetLoadPacket(game_data["current_question"]["vid"])
		await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
	
	async def CheckVideoAllLoaded():
		loaded_count = 0
		for user in USERS.values():
			if user["video_loaded"]:
				loaded_count += 1
				
		if loaded_count == len(USERS):
			for user in USERS.values():
				user["video_loaded"] = False
			await CheckQuestionNextPart()
	
	async def CheckAllGuessed(is_force=False):
		answered_count = 0
		for user in USERS.values():
			if user["guessed"] != None:
				answered_count += 1
				
		if is_force or answered_count == len(USERS):
			for user in USERS.values():
				user["guessed"] = None
			game_data["game_step"] = GAMESTEP["CHECKING"]
			# broadcast reveal answer
			packet = GetRevealAnswerPacket(game_data["current_question"]["names"])
			await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
	
	
	
	self_id = -1
	try:
		USERS[websocket] = {"name": "Anonymous", "id": -1, "video_loaded": False, "score": 0, "guessed": None}
		
		async for message in websocket:
			data = json.loads(message)
			print("[{0}] {1}".format(self_id, data))
			protocol = data["type"]
			if protocol == "name":
				if self_id == -1:
					self_id = user_idx
					user_idx += 1
						
					USERS[websocket]["id"] = self_id
					USERS[websocket]["name"] = data["name"]
					
					await websocket.send(GetUserIDPacket(self_id))
					await websocket.send(GetQuestionSetPacket(game_data["question_set"], game_data["question_count"]))
					await websocket.send(GetGameStatePacket(game_data["current_question_count"], game_data["current_question_part"]))
					
				# broadcast to all users
				packet = GetUserListPacket(list(USERS.values()))
				await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
				
			elif protocol == "upload":
				if game_data["game_step"] == GAMESTEP["IDLE"] and IsValidQuestionSet(data["data"]):
					game_data["question_set"] = data["data"]
					game_data["question_count"] = min(game_data["question_count"], len(game_data["question_set"]["questions"]))
					# broadcast question data and target question count
					packet = GetQuestionSetPacket(game_data["question_set"], game_data["question_count"])
					await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
			elif protocol == "qcount":
				if game_data["game_step"] == GAMESTEP["IDLE"] and game_data["question_set"] != None and data["count"] <= len(game_data["question_set"]["questions"]):
					game_data["question_count"] = data["count"]
					# broadcast question count
					packet = GetQuestionCountPacket(game_data["question_count"])
					await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
			elif protocol == "start":
				if game_data["game_step"] == GAMESTEP["IDLE"] and game_data["question_set"] != None:
					for user in USERS.values():
						user["score"] = 0
						
					game_data["question_pool"] = game_data["question_set"].copy()
					packet = GetStartPacket()
					await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
					
					game_data["game_step"] = GAMESTEP["WAITING"]
					game_data["current_question_count"] = 0
					await asyncio.sleep(5)
					await LoadRandomQuestion()
					
			elif protocol == "loaded":
				if game_data["game_step"] == GAMESTEP["LOADING"]:
					user = USER[websocket]
					if not user["video_loaded"]:
						user["video_loaded"] = True
						await CheckVideoAllLoaded()
			elif protocol == "guess":
				user = USERS[websocket]
				if game_data["game_step"] == GAMESTEP["PLAYING"] and user["guessed"] == None:
					user["guessed"] = data["answer"]
					# broadcast player answer
					packet = GetGuessPacket(self_id, data["answer"])
					await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
					
					if data["answer"] in game_data["current_question"]["names"]:
						USERS["score"] += 1
						# broadcast add player score
						packet = GetPlayerScorePacket(self_id)
						await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])
						
						game_data["game_step"] = GAMESTEP["CHECKING"]
						for user2 in USERS.values():
							user2["guessed"] = None
					else:
						await CheckAllGuessed()
			elif protocol == "next":
				if game_data["game_step"] == GAMESTEP["CHECKING"]:
					await CheckQuestionNextPart()
				elif game_data["game_step"] == GAMESTEP["PLAYING"]:
					await CheckAllGuessed(True)
				
	except Exception as error:
		print("[{0}] error: {1}".format(self_id, error))
		
	if self_id >= 0:
		print("[{0}] User {1} leaved".format(self_id, USERS[websocket]["name"]))
		await CheckVideoAllLoaded()
		if game_data["game_step"] == GAMESTEP["PLAYING"]:
			await CheckAllGuessed()
		
	del USERS[websocket]
	if len(USERS) > 0:
		packet = GetUserListPacket(list(USERS.values()))
		await asyncio.wait([asyncio.create_task(user.send(packet)) for user in USERS])



SETTINGS = dict()
# load settings
with open("settings.txt", "r") as f:
	settings = f.read().split("\n")
	for setting in settings:
		sep = setting.find("=")
		SETTINGS[setting[:sep].rstrip()] = setting[(sep + 1):].lstrip().rstrip()

IP = SETTINGS["IP"] if "IP" in SETTINGS else "127.0.0.1"
PORT = int(SETTINGS["PORT"]) if "PORT" in SETTINGS else 5555

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
localhost_pem = pathlib.Path(__file__).with_name("localhost.pem")
ssl_context.load_cert_chain(localhost_pem)

async def main():
	async with websockets.serve(process, IP, PORT, ssl=ssl_context):
		await asyncio.Future()  # run forever

if __name__ == "__main__":
	os.system("cls")
	print(f"Server started at {IP}:{PORT}")
	asyncio.run(main())