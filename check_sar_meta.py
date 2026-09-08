import rasterio
with rasterio.open("/Users/tanishkotian/slick_trace/backend/data/synthetic/sar/demo_scene.tif") as src:
    print(src.profile)
