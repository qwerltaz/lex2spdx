import matplotlib.pyplot as plt

maps = (
    "MapNA",
    "MapExactID",
    "MapExactMatch",
    "MapLicenseFamily",
    "MapFuzzyMatch",)
resolved_by_map = (33,
                   397,
                   261,
                   47,
                   13556)
total_names = ("Total mapped",
               "Total unresolved",
               "Dataset size")
total = (14294,
         3395,
         17689)

maps, resolved_by_map = zip(*sorted(zip(maps, resolved_by_map), key=lambda x: x[1], reverse=True))

fig, ax = plt.subplots(1, 2, figsize=(12, 6))
plt.subplots_adjust(wspace=0.5)

rot = 30

ax[0].bar(maps, resolved_by_map, color='skyblue')
ax[0].set_title('Number of Licenses Resolved by Each Mapping Method')
ax[0].set_xlabel('Mapping Method')
ax[0].set_ylabel('Count')
ax[0].set_xticklabels(maps, rotation=rot, ha='right')

ax[1].bar(total_names, total, color='salmon')
ax[1].set_title('Total Mapped vs Unresolved Licenses')
ax[1].set_xlabel('Category')
ax[1].set_ylabel('Number of Licenses')
ax[1].set_xticklabels(total_names, rotation=rot, ha='right')

plt.savefig("../../figures/mapping_distribution.png", bbox_inches='tight')
