extends RefCounted
# R2: loads an events.json file (README data contract) into a plain Dictionary
# that the renderer can step through. Static so any scene can use it.

static func load_events(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("json_loader: cannot open %s" % path)
		return {}
	var text := file.get_as_text()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("json_loader: failed to parse %s" % path)
		return {}
	return parsed
