import pandas as pd
from sklearn.model_selection import train_test_split

# Read the data
df = pd.read_csv('scripts/data/extract.csv')

# Remove rows where author_orcid is empty/null
df = df.dropna(subset=['author_orcid'])
df = df[df['author_orcid'] != '']

# Extract ORCID identifier by removing the URL prefix
df['author_orcid'] = df['author_orcid'].str.replace('https://orcid.org/', '')

# Remove duplicates while keeping all unique domain combinations for each author
df = df.drop_duplicates()

# Split the data into train (90%) and test (10%) sets
train_df, test_df = train_test_split(df, test_size=0.1, random_state=42)

# Remove 'author_id' column from train and test sets if it exists
train_df = train_df.drop(columns=['author_id'], errors='ignore')
test_df = test_df.drop(columns=['author_id'], errors='ignore')

# Create graph.csv from train.csv (without the domain column)
graph_df = train_df[['author_orcid']].drop_duplicates()

# Save the files
train_df.to_csv('scripts/data/train.csv', index=False)
test_df.to_csv('scripts/data/test.csv', index=False)
graph_df.to_csv('scripts/data/graph.csv', index=False)

# Print some statistics
print("Data processing complete:")
print(f"Original number of rows: {len(df)}")
print(f"Number of unique authors: {len(df['author_orcid'].unique())}")
print(f"Training set size: {len(train_df)}")
print(f"Test set size: {len(test_df)}")
print(f"Graph file size (unique authors): {len(graph_df)}")
print("\nDomain distribution:")
print(df['domain'].value_counts())
