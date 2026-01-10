import matplotlib.pyplot as plt

# Project names
projects = [
    "LangGraph BioFlow", "Omni Bio Lab", "scAtlas Builder",
    "bacformer-comparative-functional-pipeline", "LIMS-X",
    "RAG Gene Discovery Assistant", "DeepVariant Fine-Tuning",
    "Bioinfo LoRA Fine-Tuning", "Llama3 Protein Pathway Summarizer",
    "Workflow Doc Gen (Llama3)", "Llama3 Variant Interpretation",
    "AWS Portfolio Projects", "AI Dev Docker", "PipelineWorks",
    "Applied AI & Data Science Lab"
]

# Corresponding lines of code
loc = [
    2557, 4268, 919, 660, 6387, 684, 156, 156, 100, 34, 78, 840, 165, 465, 3248
]

# Create the bar chart
plt.figure(figsize=(14, 8))
bars = plt.barh(projects, loc, color='skyblue')
plt.xlabel("Lines of Code (LOC)")
plt.title("Project-wise Lines of Code (Past 7 Months)")
plt.gca().invert_yaxis()  # Highest LOC on top

# Add value labels
for bar in bars:
    width = bar.get_width()
    plt.text(width + 20, bar.get_y() + bar.get_height()/2,
             f'{width}', va='center')

plt.tight_layout()

# Save locally
plt.savefig("project_loc_summary.png", dpi=300, bbox_inches='tight')
print("Saved bar chart as project_loc_summary.png")

# Show chart
plt.show()
