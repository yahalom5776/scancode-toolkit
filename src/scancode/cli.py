#
# Copyright (c) 2016 nexB Inc. and others. All rights reserved.
# http://nexb.com and https://github.com/nexB/scancode-toolkit/
# The ScanCode software is licensed under the Apache License version 2.0.
# Data generated with ScanCode require an acknowledgment.
# ScanCode is a trademark of nexB Inc.
#
# You may not use this software except in compliance with the License.
# You may obtain a copy of the License at: http://apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#
# When you publish or redistribute any data created with ScanCode or any ScanCode
# derivative work, you must accompany this data with the following acknowledgment:
#
#  Generated with ScanCode and provided on an "AS IS" BASIS, WITHOUT WARRANTIES
#  OR CONDITIONS OF ANY KIND, either express or implied. No content created from
#  ScanCode should be considered or used as legal advice. Consult an Attorney
#  for any legal advice.
#  ScanCode is a free software code scanning tool from nexB Inc. and others.
#  Visit https://github.com/nexB/scancode-toolkit/ for support and download.

from __future__ import print_function, absolute_import

from collections import OrderedDict
from functools import partial
import os
from os.path import expanduser
from os.path import abspath
import sys
import traceback
from types import GeneratorType

import click
from click.termui import style
import simplejson as json

from commoncode import ignore
from commoncode import fileutils

from scancode import __version__ as version
from scancode import utils

from scancode.cache import get_scans_cache

from scancode.format import as_template
from scancode.format import as_html_app
from scancode.format import create_html_app_assets
from scancode.format import HtmlAppAssetCopyWarning
from scancode.format import HtmlAppAssetCopyError

from scancode.api import get_copyrights
from scancode.api import get_emails
from scancode.api import get_file_infos
from scancode.api import get_licenses
from scancode.api import get_package_infos
from scancode.api import get_urls


info_text = '''
ScanCode scans code and other files for origin and license.
Visit https://github.com/nexB/scancode-toolkit/ for support and download.
'''

# FIXME: we should load NOTICE instead
notice_text = '''
Software license
================

Copyright (c) 2016 nexB Inc. and others. All rights reserved.
http://nexb.com and https://github.com/nexB/scancode-toolkit/
The ScanCode software is licensed under the Apache License version 2.0.
Data generated with ScanCode require an acknowledgment.
ScanCode is a trademark of nexB Inc.

You may not use this software except in compliance with the License.
You may obtain a copy of the License at: http://apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

When you publish or redistribute any data created with ScanCode or any ScanCode
derivative work, you must accompany this data with the following acknowledgment:
'''


acknowledgment_text = '''
  Generated with ScanCode and provided on an "AS IS" BASIS, WITHOUT WARRANTIES
  OR CONDITIONS OF ANY KIND, either express or implied. No content created from
  ScanCode should be considered or used as legal advice. Consult an Attorney
  for any legal advice.
  ScanCode is a free software code scanning tool from nexB Inc. and others.
  Visit https://github.com/nexB/scancode-toolkit/ for support and download.
'''

acknowledgment_text_json = acknowledgment_text.strip().replace('  ', '')


extra_notice_text = '''

Third-party software licenses
=============================

ScanCode embeds third-party free and open source software packages under various
licenses including copyleft licenses. Some of the third-party software packages
are delivered as pre-built binaries. The origin and license of these packages is
documented by .ABOUT files.

The corresponding source code for pre-compiled third-party software is available
for immediate download from the same release page where you obtained ScanCode at:
https://github.com/nexB/scancode-toolkit/
or https://github.com/nexB/scancode-thirdparty-src/

You may also contact us to request the source code by email at info@nexb.com or
by postal mail at:
  nexB Inc., ScanCode open source code request
  735 Industrial Road, Suite #101, 94070 San Carlos, CA, USA
Please indicate in your communication the ScanCode version for which you are
requesting source code.


License for ScanCode datasets
=============================

ScanCode includes datasets (e.g. for license detection) that are dedicated
to the Public Domain using the Creative Commons CC0 1.0 Universal (CC0 1.0)
Public Domain Dedication: http://creativecommons.org/publicdomain/zero/1.0/
'''


def print_about(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(info_text + notice_text + acknowledgment_text + extra_notice_text)
    ctx.exit()


examples_text = '''
Scancode command lines examples:

(Note for Windows: use '\\' back slash instead of '/' forward slash for paths.)

Scan the 'samples' directory for licenses and copyrights. Save scan results to
an HTML app file for interactive scan results navigation. When the scan is done,
open 'scancode_result.html' in your web browser. Note that additional app files
are saved in a directory named 'scancode_result_files':

    scancode --format html-app samples/ scancode_result.html

Scan a directory for licenses and copyrights. Save scan results to an
HTML file:

    scancode --format html samples/zlib scancode_result.html

Scan a single file for copyrights. Print scan results on terminal as JSON:

    scancode --copyright samples/zlib/zlib.h

Scan a single file for licenses, print verbose progress on terminal as each file
is scanned. Save scan to a JSON file:

    scancode --license --verbose samples/zlib/zlib.h licenses.json

Scan a directory explicitly for licenses and copyrights. Redirect JSON scan
results to a file:

    scancode -f json -l -c samples/zlib/ > scan.json

To extract archives, see the 'extractcode' command instead.
'''


def print_examples(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(examples_text)
    ctx.exit()


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('ScanCode version ' + version)
    ctx.exit()


epilog_text = '''\b\bExamples (use --examples for more):

\b
Scan the 'samples' directory for licenses and copyrights.
Save scan results to a JSON file:

    scancode --format json samples scancode_result.json

\b
Scan the 'samples' directory for licenses and copyrights. Save scan results to
an HTML app file for interactive web browser results navigation. Additional app
files are saved to the 'myscan_files' directory:

    scancode --format html-app samples myscan.html

Note: when you run scancode, a progress bar is displayed with a counter of the
number of files processed. Use --verbose to display file-by-file progress.
'''


class ScanCommand(utils.BaseCommand):
    short_usage_help = '''
Try 'scancode --help' for help on options and arguments.'''


formats = ('json', 'html', 'html-app',)

def validate_formats(ctx, param, value):
    value_lower = value.lower()
    if value_lower in formats:
        return value_lower
    # render using a user-provided custom format template
    if not os.path.isfile(value):
        raise click.BadParameter('Invalid template file: "%(value)s" does not exists or is not readable.' % locals())
    return value

@click.command(name='scancode', epilog=epilog_text, cls=ScanCommand)
@click.pass_context

@click.argument('input', metavar='<input>', type=click.Path(exists=True, readable=True))
@click.argument('output_file', default='-', metavar='<output_file>', type=click.File('wb'))

@click.option('-c', '--copyright', is_flag=True, default=False, help='Scan <input> for copyrights. [default]')
@click.option('-l', '--license', is_flag=True, default=False, help='Scan <input> for licenses. [default]')
@click.option('-p', '--package', is_flag=True, default=False, help='Scan <input> for packages. [default]')
@click.option('--email', is_flag=True, default=False, help='Scan <input> for emails.')
@click.option('--url', is_flag=True, default=False, help='Scan <input> for urls.')
@click.option('-i', '--info', is_flag=True, default=False, help='Scan <input> for files information.')
@click.option('--license-score', is_flag=False, default=0, type=int, show_default=True, help='Matches with scores lower than this score are not returned. A number between 0 and 100.')

@click.option('-f', '--format', is_flag=False, default='json', show_default=True, metavar='<style>',
              help=('Set <output_file> format <style> to one of the standard formats: %s '
                    'or the path to a custom template' % ' or '.join(formats)),
              callback=validate_formats)
@click.option('--verbose', is_flag=True, default=False, help='Print verbose file-by-file progress messages.')
@click.option('--quiet', is_flag=True, default=False, help='Do not print any progress message.')

@click.help_option('-h', '--help')
@click.option('--examples', is_flag=True, is_eager=True, callback=print_examples, help=('Show command examples and exit.'))
@click.option('--about', is_flag=True, is_eager=True, callback=print_about, help='Show information about ScanCode and licensing and exit.')
@click.option('--version', is_flag=True, is_eager=True, callback=print_version, help='Show the version and exit.')

def scancode(ctx, input, output_file, copyright, license, package,
             email, url, info, license_score, format, verbose, quiet, *args, **kwargs):
    """scan the <input> file or directory for origin clues and license and save results to the <output_file>.

    The scan results are printed on terminal if <output_file> is not provided.
    """
    possible_scans = [copyright, license, package, email, url, info]
    # Default scan when no options is provided
    if not any(possible_scans):
        copyright = True
        license = True
        package = True

    scans_cache = get_scans_cache()
    try:
        files_count, results = scan(input, copyright, license, package, email, url, info, license_score, verbose, quiet, scans_cache)
        save_results(files_count, results, format, input, output_file)
    finally:
        # cleanup
        scans_cache.clear()


def scan(input_path, copyright=True, license=True, package=True,
         email=False, url=False, info=True, license_score=0,
         verbose=False, quiet=False,
         scans_cache=None):
    """
    Return a tuple of (file_count, scan_results) where scan_results is an iterable.
    Run each requested scan proper: each individual file scan is cached on disk to
    free memory. Then the whole set of scans is loaded from the cache and streamed at
    the end.
    """
    assert scans_cache

    # save paths to report paths relative to the original input
    original_input = fileutils.as_posixpath(input_path)
    abs_input = fileutils.as_posixpath(os.path.abspath(os.path.expanduser(input_path)))

    get_licenses_with_score = partial(get_licenses, min_score=license_score)

    # note: "flag and function" expressions return the function if flag is True
    # note: the order of the scans matters to show things in logical order
    scanners = OrderedDict([
        # ('infos' , info and get_file_infos),
        ('licenses' , license and get_licenses_with_score),
        ('copyrights' , copyright and get_copyrights),
        ('packages' , package and get_package_infos),
        ('emails' , email and get_emails),
        ('urls' , url and get_urls),
    ])

    # note: we inline progress display functions to close on some args

    def scan_start():
        """Progress event displayed at start of scan"""
        return style('Scanning files...', fg='green')

    def scan_event(item):
        """Progress event displayed each time a file is scanned"""
        if item:
            line = verbose and item or fileutils.file_name(item) or ''
            return 'Scanning: %(line)s' % locals()

    def scan_end():
        """Progress event displayed at end of scan"""
        has_warnings = False
        has_errors = False
        summary = []
        summary_color = 'green'
        summary_color = has_warnings and 'yellow' or summary_color
        summary_color = has_errors and 'red' or summary_color
        summary.append(style('Scanning done.', fg=summary_color, reset=True))
        return '\n'.join(summary)

    ignored = partial(ignore.is_ignored, ignores=ignore.ignores_VCS, unignores={})
    resources = fileutils.resource_iter(abs_input, ignored=ignored)

    with utils.progressmanager(resources,
                               item_show_func=scan_event,
                               start_show_func=scan_start,
                               finish_show_func=scan_end,
                               verbose=verbose,
                               show_pos=True,
                               quiet=quiet
                               ) as progressive_resources:

        for files_count, resource in enumerate(progressive_resources):
            # actual path of the file being scanned
            res = fileutils.as_posixpath(resource)
            # fix paths: keep the path as relative to the original input
            relative_path = utils.get_relative_path(original_input, abs_input, res)

            # always fetch infos and cache.
            infos = scan_infos(res)
            is_cached = scans_cache.put_infos(relative_path, infos)

            # Skip other scans if already cached
            if is_cached:
                continue
            scan_result = scan_one(res, scanners)
            scans_cache.put_scan(relative_path, infos, scan_result)
        files_count += 1
    return files_count, scans_cache.iterate(with_infos=info)


def scan_infos(input_file):
    """
    Scan one file or directory and return file_infos data. This may contain an
    'errors' key with a list of error messages.
    """
    infos = OrderedDict()
    errors = []
    try:
        infos = get_file_infos(input_file, as_list=False)
    except Exception, e:
        # never fail but instead add an error message.
        errors = dict(infos=(e.message, traceback.format_exc(),))
    # put errors last
    infos['scan_errors'] = errors
    return infos


def scan_one(input_file, scans):
    """
    Scan one file or directory and return a scanned data, calling every scan in
    the `scans` mapping of (scan name -> scan function). This may contain an
    'errors' key with a list of error messages.
    """
    scan_result = OrderedDict()
    errors = []
    for scan_name, scan_func in scans.items():
        if not scan_func:
            continue
        scan_errors = dict()
        try:
            scan_details = scan_func(input_file)
            # consume generators
            if isinstance(scan_details, GeneratorType):
                scan_details = list(scan_details)
            scan_result[scan_name] = scan_details
        except Exception, e:
            # never fail but instead add an error message and keep an empty scan:
            scan_result[scan_name] = []
            scan_errors[scan_name] = (e.message, traceback.format_exc(),)
            errors.append(scan_errors)
    # put errors last
    scan_result['scan_errors'] = errors
    return scan_result


def save_results(files_count, scanned_files, format, input, output_file):
    """
    Save results to file or screen.
    """
    if output_file != sys.stdout:
        parent_dir = os.path.dirname(output_file.name)
        if parent_dir:
            fileutils.create_dir(abspath(expanduser(parent_dir)))

    if format and format not in formats:
        # render using a user-provided custom format template
        if not os.path.isfile(format):
            click.secho('\nInvalid template passed.', err=True, fg='red')
        else:
            output_file.write(as_template(scanned_files, template=format))

    elif format == 'html':
        output_file.write(as_template(scanned_files))

    elif format == 'html-app':
        output_file.write(as_html_app(input, output_file))
        try:
            create_html_app_assets(scanned_files, output_file)
        except HtmlAppAssetCopyWarning:
            click.secho('\nHTML app creation skipped when printing to terminal.',
                       err=True, fg='yellow')
        except HtmlAppAssetCopyError:
            click.secho('\nFailed to create HTML app.', err=True, fg='red')

    elif format == 'json':
        meta = OrderedDict()
        meta['scancode_notice'] = acknowledgment_text_json
        meta['scancode_version'] = version
        meta['files_count'] = files_count
        # TODO: add scanning options to meta
        meta['files'] = scanned_files
        # json.dump(meta, output_file, indent=2)
        json.dump(meta, output_file, indent=2 * ' ', iterable_as_array=True)
    else:
        raise Exception('unknown format')
