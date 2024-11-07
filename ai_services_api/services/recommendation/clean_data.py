import pandas as pd
from sklearn.model_selection import train_test_split

# Define file paths
input_file = "scripts/data/test5.csv"
train_file = "scripts/data/train.csv"
test_file = "scripts/data/test.csv"
graph_file = "scripts/data/graph.csv"

# Load the CSV file
df = pd.read_csv(input_file)

# Drop the 'author_id' column
df = df.drop(columns=['author_id'])

# Remove rows where 'author_orcid' is empty
df = df.dropna(subset=['author_orcid'])

# Remove rows with "Unknown Domain" in 'domain', "Unknown Field" in 'field', or "Unknown Subfield" in 'subfield'
df = df[
    (df['domain'] != "Unknown Domain") &
    (df['field'] != "Unknown Field") &
    (df['subfield'] != "Unknown Subfield")
]

# Split data into 90% train and 10% test
train_df, test_df = train_test_split(df, test_size=0.1, random_state=42)

# Save the train and test data to CSV files
train_df.to_csv(train_file, index=False)
test_df.to_csv(test_file, index=False)

# Create graph.csv with only 'author_orcid' from train data
graph_df = train_df[['author_orcid']]
graph_df.to_csv(graph_file, index=False)

print("Data processing complete. Files saved as train.csv, test.csv, and graph.csv in the scripts/data folder.")
