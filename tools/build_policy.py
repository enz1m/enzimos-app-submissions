"""Manifest policy shared by the public builder and the developer portal."""
import copy
import ipaddress
import re
import urllib.parse

SHA = re.compile(r'[0-9a-f]{40}')
APP = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}')
REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
RUST_SDK = 'org.freedesktop.Sdk.Extension.rust-stable'


def require(value, message):
    if not value:
        raise ValueError(message)


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def manifest_id(manifest):
    """Narrow discovery to application manifests while retaining invalid recipes for feedback."""
    if isinstance(manifest, dict) and {'runtime', 'sdk', 'modules'} <= manifest.keys():
        value = manifest.get('app-id', manifest.get('id'))
        if isinstance(value, str) and APP.fullmatch(value):
            return value
    return None


def public_https(value, *, fragment=False):
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        return False
    try:
        url = urllib.parse.urlsplit(value)
        host = url.hostname
        if (url.scheme != 'https' or not host or url.username is not None
                or url.password is not None or url.query or (url.fragment and not fragment)):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host and not host.endswith(('.local', '.localhost', '.internal', '.invalid', '.test'))
    except ValueError:
        return False


def screenshot_dimensions(width, height):
    if width >= height:
        return 640 <= width <= 3840 and 360 <= height <= 2160
    return 360 <= width <= 2160 and 540 <= height <= 3840


def resolve(manifest, repository, commit):
    manifest = copy.deepcopy(manifest)
    require(isinstance(manifest, dict), 'The Flatpak manifest must be a JSON object.')
    manifest.setdefault('branch', 'stable')

    def pin(modules, depth=0):
        require(isinstance(modules, list) and 0 < len(modules) <= 100 and depth <= 8,
                'Declare modules directly in the JSON manifest.')
        for module in modules:
            require(isinstance(module, dict), 'Expand external module includes into the JSON manifest.')
            sources = module.get('sources', [])
            require(isinstance(sources, list), 'Declare module sources as a list.')
            for source in sources:
                require(isinstance(source, dict), 'Declare every source directly in the JSON manifest.')
                if source.get('commit') == '@ENZIM_SOURCE_COMMIT@':
                    url = source.get('url')
                    require(isinstance(url, str) and url.rstrip('/').removesuffix('.git') == 'https://github.com/' + repository,
                            'Use @ENZIM_SOURCE_COMMIT@ only for the selected repository.')
                    source['commit'] = commit
            if 'modules' in module:
                pin(module['modules'], depth + 1)

    pin(manifest.get('modules'))
    return manifest


def inspect(manifest, repository, commit, app_id):
    require(matches(SHA, commit) and matches(APP, app_id) and matches(REPOSITORY, repository),
            'Invalid app, repository or commit.')
    manifest = resolve(manifest, repository, commit)
    require(manifest_id(manifest) == app_id and manifest.get('id', app_id) == app_id,
            'The Flatpak application ID must match the listing.')
    require(manifest['branch'] == 'stable', 'Use the stable Flatpak branch for publication.')
    for key in ('runtime', 'sdk'):
        require(matches(r'org\.(freedesktop|gnome|kde)\.[A-Za-z0-9_.-]+', manifest.get(key)),
                'Select a Freedesktop, GNOME or KDE runtime and SDK from Flathub.')
    require(matches(r'[A-Za-z0-9_.-]{1,50}', manifest.get('runtime-version')), 'Specify a runtime version.')
    require(matches(r'[A-Za-z0-9_.-]{1,100}', manifest.get('command')), 'Specify the app executable in command.')
    extensions = manifest.get('sdk-extensions', [])
    require(extensions == [] or (extensions == [RUST_SDK] and manifest['sdk'] == 'org.freedesktop.Sdk'),
            f'The only supported SDK extension is {RUST_SDK}, with the Freedesktop SDK.')
    matched = False
    sources = []

    def check_options(node, *, top_level=False):
        blocked = {'build-args', 'platform-extensions', 'extra-data', 'add-extensions',
                   'build-extensions', 'add-build-extensions'}
        if not top_level:
            blocked.add('sdk-extensions')
        forbidden = sorted(blocked & node.keys())
        require(not forbidden, 'Remove unsupported build options: ' + ', '.join(forbidden))
        if 'build-options' in node:
            options = node['build-options']
            require(isinstance(options, dict), 'Build options must be a JSON object.')
            require(not (blocked | {'sdk-extensions'}) & options.keys(),
                    'Remove host build arguments and extension declarations from build-options.')

    def check_modules(modules):
        nonlocal matched
        for module in modules:
            check_options(module)
            for source in module.get('sources', []):
                kind = source.get('type')
                require(kind in ('git', 'archive', 'file'), 'Use declared Git, archive or file sources.')
                url = source.get('url')
                require(public_https(url) and urllib.parse.urlsplit(url).port is None,
                        'Use a public HTTPS URL for each source, without credentials, queries or fragments.')
                require(not {'branch', 'tag', 'commands', 'path', 'paths', 'mirror-urls'} & source.keys(),
                        'Remove moving refs and undeclared source inputs.')
                if kind == 'git':
                    require(matches(SHA, source.get('commit')), 'Pin each Git dependency to a full commit.')
                    require(source.get('disable-submodules') is True,
                            'Declare dependencies explicitly and set disable-submodules to true.')
                    if url.rstrip('/').removesuffix('.git') == 'https://github.com/' + repository and source['commit'] == commit:
                        matched = True
                else:
                    require(matches(r'[0-9a-f]{64}', source.get('sha256')), 'Set a SHA-256 checksum for each downloaded file or archive.')
                sources.append({key: source[key] for key in ('type', 'url', 'commit', 'sha256') if key in source})
            if 'modules' in module:
                check_modules(module['modules'])

    check_options(manifest, top_level=True)
    check_modules(manifest['modules'])
    require(matched, 'Include the selected repository as a Git source at the release commit. Use @ENZIM_SOURCE_COMMIT@ in the recipe.')
    permissions = manifest.get('finish-args', [])
    require(isinstance(permissions, list) and len(permissions) <= 100
            and all(isinstance(value, str) and value.startswith('--') and '\n' not in value for value in permissions)
            and len(set(permissions)) == len(permissions), 'List each Flatpak permission once in finish-args.')
    return {'sources': sources, 'permissions': permissions, 'runtime': manifest['runtime'],
            'sdk': manifest['sdk'], 'runtime_version': manifest['runtime-version']}
