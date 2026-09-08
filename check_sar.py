import rasterio
sar_path = "/Users/tanishkotian/slick_trace/backend/data/synthetic/sar/demo_scene.tif"
with rasterio.open(sar_path) as src:
    print("Shape:", src.shape)
    print("Nodata:", src.nodata)
