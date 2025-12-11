# current MMDD_HHmm
current_time=$(date +%m%d_%H%M)
# make a directory with this name under logs/important

target_dir="logs/important/$current_time"
mkdir -p "$target_dir"
mkdir -p "$target_dir/logs"
mkdir -p "$target_dir/patches"

mv logs/logs/*.log "$target_dir"/logs
mv logs/patches/*.patch "$target_dir"/patches