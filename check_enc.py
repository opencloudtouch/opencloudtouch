import os
test_dir = 'apps/frontend/tests/e2e'
for fname in sorted(os.listdir(test_dir)):
    if fname.endswith('.cy.ts'):
        path = os.path.join(test_dir, fname)
        with open(path, 'rb') as f:
            data = f.read()
        text = data.decode('utf-8-sig', errors='ignore')
        corrupted = any(c in text for c in ['Ã¤', 'Ã¼', 'Ã¶', 'Ã–', 'Ãœ', 'Ã„', 'Ã©', 'Ã¨', 'Ã¤'])
        print(f'{fname}: corrupted={corrupted}')
