import pandas as pd

# Load the CSV file
file_path = 'scripts/data/train.csv'
df = pd.read_csv(file_path)

# Group by 'field' and 'subfield', and select groups with unique 'author_orcid'
similar_rows = []
for _, group in df.groupby(['field', 'subfield']):
    unique_orcids = group['author_orcid'].nunique()
    if unique_orcids > 1:  # Ensure there are at least 2 different 'author_orcid' values
        similar_rows.append(group)

# Limit to two groups of similar rows as requested
try_df = pd.DataFrame(columns=df.columns)
for group in similar_rows[:2]:  # Only take the first two groups if there are more
    try_df = pd.concat([try_df, group])

# Save the similar rows as try.csv
try_df.to_csv('try.csv', index=False)

print("Similar rows saved to try.csv")
