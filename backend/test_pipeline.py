from app.pipeline.stage0_perception import run_stage0
res = run_stage0(run_id="test_run", input_path="data/synthetic/sar/demo_scene.tif")
print(res)
