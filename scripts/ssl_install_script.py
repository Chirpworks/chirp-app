import ssl
import certifi


def run():
    # Set default HTTPS context with Certifi's certificates
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(certifi.where())

    print("SSL certificates updated successfully!")


if __name__ == "__main__":
    run()
