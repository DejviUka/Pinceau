# config_transcribe.py

# Device: "cuda" or "cpu"
device = "cpu"

# Model size: tiny, base, small, medium, large-v2, large-v3
model_size = "large-v3"

# Precision: "float32", "float16", or "int8"
compute_type = "float32"

# Language code for transcription: "en", "es", "it". Set to None to auto-detect
language = "en"

# Alignment model name, set to None to use default. For English, "WAV2VEC2_ASR_LARGE_960H" can be used for potentially better alignment.
alignment_model = "WAV2VEC2_ASR_LARGE_960H"

# For slicer.py only: desired non‐speech interval between clips (seconds)
# slicer will add half of this before and after each kept sentence
SILENCE_BETWEEN_CLIPS_S = 0.7