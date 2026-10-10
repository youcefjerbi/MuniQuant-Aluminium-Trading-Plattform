"""Example upstream-package consumer: no application database or private system access."""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker

def consume(path,schema_path):
    package=json.loads(Path(path).read_text())
    Draft202012Validator(json.loads(Path(schema_path).read_text()),format_checker=FormatChecker()).validate(package)
    docs={d['document_id']:d for d in package['documents']}
    sources={s['source_id']:s for s in package['sources']}
    rows=[]
    for record in package['records']:
        document=docs[record['document_id']];source=sources[record['source_id']]
        if document['source_id']!=source['source_id'] or document['content_hash']!=record['content_hash']:
            raise ValueError('Broken provenance join')
        rows.append({'entity':record['canonical_name'],'attribute':record['attribute_type'],
                     'value':str(Decimal(record['normalized_value'])) if record['normalized_value'] is not None else record['reported_value'],
                     'unit':record['unit'],'valid_from':record['valid_from'],'publisher':source['publisher'],
                     'source_url':document['original_url'],'content_hash':document['content_hash'],'locator':record['evidence_reference']})
    return {'package_version':package['package_version'],'records':rows}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package');parser.add_argument('--schema',default='app/evidence-v1.schema.json')
    args=parser.parse_args();print(json.dumps(consume(args.package,args.schema),indent=2))
if __name__=='__main__': main()
