with open(r"D:\驷马仓库\ad-compliance-checker\libang-custom\4ma_wang_portal.html", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines[77:83], start=78):
    print(f"Line {i}: {repr(line)}")
