import hashlib

# def hash_password(password):
#     return hashlib.sha512(password.encode()).hexdigest()
#
# def verify_password(input_password, stored_hash):
#     return hash_password(input_password) == stored_hash
#
# # Example Usage
# user_input = "mypassword123"
# stored_hash = "5e884898da28047151d0e56f8dc6292773603d0d6aabbddcba89a9ad5a6547d77a5a0c1cf8327eaecc6ab0dcf3fc3ecf0c8871c50cc27e5f6a44b6497c55e3bf"
#
# if verify_password(user_input, stored_hash):
#     print("Password is correct!")
# else:
#     print("Incorrect password.")

import scipy.cluster.hierarchy as sch

def run():
    # from itertools import permutations
    #
    # words = ["COMMERCIAL", "CVM", "SIXDEE", "20JAN2025", "20JANUARY2025", "JAN2025", "JANUARY2025", "PROPOSAL", "MKT", "PRICELIST"]
    # # words = ["SIXDEE", "COMMERCIAL", "PROPOSAL", "DOCUMENT", "VERSION", "V", "20", "25", "2025", "JAN", "JANUARY", "MKT", "CVM", "1", "_", "@", "^", "6", "d", "D", "6d", "6D", "^d", "^D", "sixdee", "commercial", "proposal", "document", "version", "v", "jan", "january", "mkt", "cvm"]
    # with open("middle_combinations_1.txt", "w") as f:
    #     for i in range(1, len(words) + 1):
    #         for perm in permutations(words, i):
    #             f.write("".join(perm) + "\n")
    print(sch.__doc__)


if __name__=='__main__':
    run()
