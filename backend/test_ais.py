from app.services.ais_loader import load_and_filter
res = load_and_filter(csv_path="/Users/tanishkotian/slick_trace/backend/data/synthetic/ais/demo_ais.csv", bbox=[28.44, -90.1, 28.52, -89.95])
print(res)
