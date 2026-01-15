# Database Migration Tool

This folder contains tools for migrating old database backups to the new schema.

## What Changed in the New Schema?

### Old Schema (Before):
- `marks_obtained`: INTEGER
- `grade_point`: INTEGER
- `total_obtained`, `total_max`: INTEGER
- 7 grading rules with gaps (e.g., 79-80% would get F grade)

### New Schema (After):
- `marks_obtained`: REAL (supports decimals like 8.5)
- `grade_point`: REAL (supports decimals like 9.5)
- `total_obtained`, `total_max`: REAL
- 8 grading rules with proper decimal ranges (no gaps)

## New Grading Rules

| Range | Grade | Points |
|-------|-------|--------|
| 90.0 - 100.0% | O | 10 |
| 80.0 - 89.99% | A+ | 9 |
| 70.0 - 79.99% | A | 8 |
| 60.0 - 69.99% | B+ | 7 |
| 55.0 - 59.99% | B | 6 |
| 50.0 - 54.99% | C | 5 |
| 40.0 - 49.99% | P | 4 |
| 0.0 - 39.99% | F | 0 |

## Usage

### Command Line:

```bash
# Basic usage
python migrate_database.py old_backup.db

# Specify output filename
python migrate_database.py old_backup.db new_database.db
```

### From Admin Dashboard:

1. Go to Admin Dashboard
2. Click "Backup/Restore" button
3. Upload your old backup file
4. Click "Migrate Database" button
5. System will automatically convert and apply the new schema

## What Gets Migrated?

✅ **Preserved:**
- All users (students and admin)
- All presets
- All subjects and components
- All student marks (converted to REAL)
- All CGPA records

⚠️ **Updated:**
- Grading rules (7 → 8 rules)
- Student grades (recalculated with new rules)
- Grade points (may change due to new rules)

## Important Notes

- **Backup First**: Always backup your current database before migration
- **Grade Changes**: Some students' grades may change due to new grading rules
- **CGPA Recalculation**: CGPA values may need recalculation if grades changed
- **One-Way Process**: Migration is one-way (old → new)

## Example Output

```
🔄 Starting migration from: old_backup.db
📦 Output will be saved to: migrated_database.db

📖 Reading old database...
   ✓ Found 25 users
   ✓ Found 5 presets
   ✓ Found 30 subjects
   ✓ Found 90 components
   ✓ Found 450 student marks
   ✓ Found 150 subject results
   ✓ Found 25 CGPA records

🔨 Creating new database with updated schema...
   ✓ New schema created

📝 Migrating data...
   ✓ Migrated 25 users
   ✓ Migrated 5 presets
   ✓ Migrated 30 subjects
   ✓ Migrated 90 components
   ✓ Migrated 450 student marks (converted to REAL)
   ✓ Migrated 150 subject results
   ⚠️  Recalculated 12 grades due to new grading rules
   ✓ Migrated 25 CGPA records

✅ Migration completed successfully!
```
