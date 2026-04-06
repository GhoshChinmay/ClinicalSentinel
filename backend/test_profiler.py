import cProfile
import pstats
import sys
import os
import uuid
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engines.detection import process_and_detect

def main():
    session_id = str(uuid.uuid4())
    print("Starting process_and_detect...")
    process_and_detect(file_path="data/creditcard.csv", session_id=session_id)

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    main()
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumtime')
    stats.print_stats(30)
