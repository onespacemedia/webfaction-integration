from django.core.management.base import BaseCommand

import imp
import importlib
import urllib
import os
import re
import xmlrpclib


class Command(BaseCommand):

    def handle(self, *args, **options):
        # Load the settings.
        settings_base = os.environ.get("DJANGO_SETTINGS_MODULE")
        project_name = settings_base.replace('.settings', '')

        settings = imp.load_source('production_settings', './{project}/settings/production.py'.format(
            project=project_name
        ))

        local_settings = importlib.import_module('{base}.local'.format(
            base=settings_base
        ))

        # Check to see whether the Webfaction details are in the settings.
        try:
            webfaction_username = settings.WEBFACTION_USERNAME
            webfaction_password = settings.WEBFACTION_PASSWORD
        except:
            webfaction_username = raw_input("Webfaction Username: ")
            webfaction_password = raw_input("Webfaction Password: ")

        # Connect to the Webfaction API.
        server = xmlrpclib.ServerProxy('https://api.webfaction.com/')
        session_id, account = server.login(webfaction_username, webfaction_password)

        # Make sure the production.py has the right settings.
        if settings.DATABASES['default']['NAME'] != webfaction_username:
            exit('Database name is incorrect. (Expected {expected}, got {got})'.format(
                expected=webfaction_username,
                got=settings.DATABASES['default']['NAME']
            ))
        if settings.DATABASES['default']['USER'] != webfaction_username:
            exit('Database user is incorrect. (Expected {expected}, got {got})'.format(
                expected=webfaction_username,
                got=settings.DATABASES['default']['USER']
            ))

        expected_media_root = '/home/{username}/webapps/{username}_media'.format(
            username=webfaction_username
        )
        if settings.MEDIA_ROOT != expected_media_root:
            exit('Media root is incorrect. (Expected: {expected})'.format(
                expected=expected_media_root
            ))

        expected_static_root = '/home/{username}/webapps/{username}_static'.format(
            username=webfaction_username
        )
        if settings.STATIC_ROOT != '/home/{username}/webapps/{username}_static'.format(username=webfaction_username):
            exit('Static root is incorrect. (Expected: {expected})'.format(
                expected=expected_static_root
            ))

        # Check the allowed hosts.
        if '{username}.webfactional.com'.format(username=webfaction_username) not in settings.ALLOWED_HOSTS:
            exit('You need to fix your ALLOWED_HOSTS.')

        # Get the list of applications which are currently on the account.
        apps = server.list_apps(session_id)

        if len(apps) > 0:
            print 'There {are} currently {num} app{s} installed on the server. If you would like to delete {any}, please enter {ids}.'.format(
                num=len(apps),
                are='are' if len(apps) != 1 else 'is',
                s='s' if len(apps) != 1 else '',
                any='any' if len(apps) != 1 else 'it',
                ids='their IDs, seperated by commas' if len(apps) != 1 else 'the ID'
            )

            print ''

            app_dict = {}

            for app in apps:
                app_dict[app['id']] = app['name']

                print "[{id}] {name} ({type})".format(
                    id=app['id'],
                    name=app['name'],
                    type=app['type']
                )

            print ''

            application_ids = raw_input('Please enter the IDs of any applications you wish to delete: (leave blank for none) ')

            if application_ids != '':
                for application_id in application_ids.split(','):
                    application_id = int(application_id)

                    print 'Deleting {name}.'.format(
                        name=app_dict[application_id]
                    )

                    server.delete_app(session_id, app_dict[application_id])

        # Create the applications we need.
        # django151_mw34_27 - Django 1.5.1

        # Create the main application.
        print 'Creating the main Django application.'
        try:
            server.create_app(session_id, webfaction_username, 'django151_mw34_27')
        except:
            pass

        # Create the media application.
        print 'Creating the media application.'
        try:
            server.create_app(session_id, webfaction_username + '_media', 'static_only', False, 'expires max')
        except:
            pass

        # Create the static application.
        print 'Creating the static application.'
        try:
            server.create_app(session_id, webfaction_username + '_static', 'static_only')
        except:
            pass

        # Add the www. subdomain for the webfactional domain.
        print 'Adding the www subdomain.'
        try:
            server.create_domain(session_id, webfaction_username + '.webfactional.com', 'www')
        except:
            pass

        # Update the 'website' to have our new applications & subdomain.
        print 'Creating the \'website\'.'
        try:
            server.update_website(session_id, webfaction_username, '', False, [
                '{}.webfactional.com'.format(webfaction_username),
                'www.{}.webfactional.com'.format(webfaction_username)
            ],
                (webfaction_username, '/'),
                (webfaction_username + '_media', '/media'),
                (webfaction_username + '_static', '/static'),
            )
        except:
            pass

        # Add the mailbox, if it doesn't already exist.
        print 'Creating the mailbox.'
        try:
            server.create_mailbox(session_id, webfaction_username)
        except:
            pass

        try:
            server.change_mailbox_password(session_id, webfaction_username, webfaction_password)
        except:
            pass

        # Create the database.
        database_password = urllib.urlopen('https://www.random.org/strings/?num=1&len=8&digits=on&loweralpha=on&unique=on&format=plain&rnd=new').read().rstrip()

        print 'Creating the database.'
        try:
            server.create_db(session_id, webfaction_username, 'postgresql', database_password)
            print 'Database password: {}'.format(database_password)
            raw_input('When you have updated production.py with the new password, press Enter to continue.')
        except:
            # By getting it from the settings, we can continue an install without problems.
            database_password = settings.DATABASES['default']['PASSWORD']

        # Add the local SSH public key to the authorized_keys file on the new server.
        print 'Adding SSH public key to server.'
        commands = 'mkdir ~/.ssh &&'
        commands += 'touch ~/.ssh/authorized_keys &&'

        with open(os.path.expanduser("~/.ssh/id_rsa.pub"), 'r') as f:
            contents = f.read()
            commands += 'echo "{}" >> ~/.ssh/authorized_keys &&'.format(contents)

        commands += 'chmod 755 ~/.ssh &&'
        commands += 'chmod 600 ~/.ssh/authorized_keys'

        try:
            server.system(session_id, commands)
        except Exception as e:
            print e

        # Add the .pgpass file.
        print 'Creating .pgpass file.'
        commands = 'echo "localhost:5432:{username}:{username}:{password}" > ~/.pgpass &&'.format(
            username=webfaction_username,
            password=database_password
        )
        commands += 'chmod 600 ~/.pgpass'

        try:
            server.system(session_id, commands)
        except Exception as e:
            print e

        # Create a Git repo on the server.
        print 'Creating remote Git repo.'
        commands = 'mkdir ~/repos &&'
        commands += 'git init ~/repos/{username} --bare'.format(
            username=webfaction_username
        )

        try:
            server.system(session_id, commands)
        except Exception as e:
            print e

        # Check for a local Git repo, create it if it doesn't exist.
        print 'Checking for a local Git repo.'
        if not os.path.exists('.git'):
            os.system('git init')
            os.system('git add .')
        os.system('git commit -am "Initial commit"')

        # Add the remote Git repo.
        os.system('git remote add origin {username}@{username}.webfactional.com:~/repos/{username}'.format(
            username=webfaction_username
        ))
        os.system('git push origin master')

        # Push the local DB up to the server.
        print 'Pushing the local database up.'
        os.system('pushdb {username} {username} {local_database}'.format(
            username=webfaction_username,
            local_database=local_settings.DATABASES['default']['NAME']
        ))

        # Push the static files up.
        print 'Pushing the local media files up.'
        media_directory = re.search('\/Sites\/(\w+)\/media', local_settings.MEDIA_ROOT).group(1)
        os.system('pushmedia {username} {username} {media_directory}'.format(
            username=webfaction_username,
            media_directory=media_directory
        ))

        # Push the helper scripts up.
        print 'Pushing the helper scripts up.'
        os.system('bootstrap_webfaction {username}'.format(
            username=webfaction_username
        ))

        # Install the CMS and supporting libraries.
        print 'Installing the CMS things..'
        command = '~/bin/install_cms {username}'.format(
            username=webfaction_username
        )

        try:
            server.system(session_id, command)
        except:
            # easy_install likes to be noisy, which makes XML-RPC cry.
            pass

        # Update the Apache configuration.
        print 'Updating the Apache configuration.'
        apache_conf = 'webapps/{username}/apache2/conf/httpd.conf'.format(
            username=webfaction_username
        )

        replace_script_alias = (
            '/home/{username}/webapps/{username}/myproject/myproject/wsgi.py'.format(
                username=webfaction_username
            ),
            '/home/{username}/webapps/{username}/lib/{username}/{project}/wsgi.py'.format(
                username=webfaction_username,
                project=project_name
            ),
        )

        replace_daemon_process = (
            '/home/{username}/webapps/{username}/myproject'.format(
                username=webfaction_username
            ), '/home/{username}/webapps/{username}/lib/{username}'.format(
                username=webfaction_username
            )
        )

        try:
            server.replace_in_file(session_id, apache_conf, replace_script_alias, replace_daemon_process)
        except Exception as e:
            print e

        try:
            server.system(session_id, '~/bin/update_app {username}'.format(
                username=webfaction_username
            ))
        except Exception as e:
            print e

        print '..and we\'re done! http://{username}.webfactional.com'.format(
            username=webfaction_username
        )
